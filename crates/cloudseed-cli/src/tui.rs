//! Terminal UI for cloudseed.
//!
//! Layout: a horizontal menu bar on top, a command list on the left, and an
//! action panel on the right that shows a form (Generate/Validate/Completion),
//! the hierarchical region/city timezone picker, or command output.
//!
//! Key bindings depend on the focused region:
//! - Menu bar:     ←/→ move, Enter opens, Esc/q/Q quits
//! - Command list: ↑/↓ move, Enter runs, Esc returns to the menu bar
//! - Form:         ↑/↓ field, type to edit, Enter submits, Esc returns
//! - Timezone:     ↑/↓ move in the focused column, ←/→ switch column,
//!   Enter picks the zone, Esc returns

use crossterm::{
    event::{self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode, KeyEventKind},
    execute,
    terminal::{self, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{
    prelude::*,
    widgets::{Block, Borders, Clear, List, ListItem, ListState, Paragraph, Wrap},
};
use std::{
    io,
    path::Path,
    time::{Duration, Instant},
};

use super::{
    cmd_completion, cmd_generate, cmd_validate, set_timezone, COMMON_TIMEZONES, TIMEZONE_REGIONS,
};

/// How long a toast stays on screen.
const TOAST_TTL: Duration = Duration::from_secs(4);

/// Shells the completion command accepts.
const SHELLS: &[&str] = &["bash", "zsh", "fish"];

/// Menu bar entries, in order.
const MENU: &[&str] = &["Generate", "Validate", "Completion", "Timezone"];

/// Config path used when the TUI is started without `--config`.
const DEFAULT_CONFIG: &str = "./cloudseed.yaml";

/// Which screen has keyboard focus.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Screen {
    MenuBar,
    CommandList,
    Form,
    Timezone,
    Output,
}

/// Which of the timezone picker's two columns has focus.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum TzColumn {
    Region,
    City,
}

/// What the action panel is currently showing.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Panel {
    Idle,
    Generate,
    Validate,
    Completion,
    Timezone,
}

/// Severity of a toast message.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum ToastKind {
    Success,
    Error,
}

/// A toast: short message plus when it was raised.
struct Toast {
    message: String,
    kind: ToastKind,
    raised_at: Instant,
}

/// Region/city selection state for the timezone picker.
struct TimezoneState {
    region: usize,
    city: usize,
    column: TzColumn,
    /// Zone typed by hand via the trailing "Custom…" entry.
    custom: String,
}

/// A single editable form field.
struct Field {
    label: &'static str,
    value: String,
    /// Set by `validate_form`; cleared whenever the value is edited.
    error: Option<String>,
}

/// The TUI application.
pub struct App {
    /// Config file the Timezone menu edits and the forms pre-fill.
    config_path: Option<String>,
    screen: Screen,
    panel: Panel,
    menu_index: usize,
    command_index: usize,
    /// Command list entries for the current menu selection.
    command_items: Vec<String>,
    /// Index of the focused form field.
    field_index: usize,
    fields: Vec<Field>,
    tz: TimezoneState,
    /// Region names plus a trailing "Custom…" entry.
    regions: Vec<String>,
    /// Zones belonging to the selected region; empty for "Custom…".
    cities: Vec<String>,
    /// Output of the last run, shown when `Screen::Output` is active.
    output: String,
    output_error: bool,
    toast: Option<Toast>,
}

impl App {
    /// Create the TUI. `config_path` is the file the Timezone menu edits and
    /// pre-fills the Generate/Validate forms.
    ///
    /// When it is `None` the path fields start on [`DEFAULT_CONFIG`]; editing
    /// and running still works, so the TUI is fully usable without `--config`.
    pub fn new(config_path: Option<String>) -> Self {
        let regions = TIMEZONE_REGIONS
            .iter()
            .map(|r| r.to_string())
            .chain(std::iter::once("Custom…".to_string()))
            .collect();
        let config_path = Some(config_path.unwrap_or_else(|| DEFAULT_CONFIG.to_string()));

        Self {
            config_path,
            screen: Screen::MenuBar,
            panel: Panel::Idle,
            menu_index: 0,
            command_index: 0,
            command_items: Vec::new(),
            field_index: 0,
            fields: Vec::new(),
            tz: TimezoneState {
                region: 0,
                city: 0,
                column: TzColumn::Region,
                custom: String::new(),
            },
            regions,
            cities: cities_for(0).iter().map(|s| s.to_string()).collect(),
            output: String::new(),
            output_error: false,
            toast: None,
        }
    }

    /// Run the event loop until the user quits.
    pub fn run(&mut self) -> io::Result<()> {
        terminal::enable_raw_mode()?;
        let mut stdout = io::stdout();
        execute!(stdout, EnterAlternateScreen, EnableMouseCapture)?;
        let backend = CrosstermBackend::new(stdout);
        let mut term = Terminal::new(backend)?;

        let result = self.event_loop(&mut term);

        // Restore the terminal even when the loop errored, then report it.
        terminal::disable_raw_mode()?;
        execute!(
            term.backend_mut(),
            LeaveAlternateScreen,
            DisableMouseCapture
        )?;
        result
    }

    fn event_loop(&mut self, term: &mut Terminal<CrosstermBackend<io::Stdout>>) -> io::Result<()> {
        let tick = Duration::from_millis(200);
        let mut last = Instant::now();

        loop {
            term.draw(|f| self.draw(f))?;

            let timeout = tick.checked_sub(last.elapsed()).unwrap_or_default();
            if event::poll(timeout)? {
                if let Event::Key(key) = event::read()? {
                    if key.kind == KeyEventKind::Press && self.on_key(key.code) {
                        break;
                    }
                }
            }
            if last.elapsed() >= tick {
                last = Instant::now();
                self.expire_toast();
            }
        }
        Ok(())
    }

    /// Handle a key press. Returns true when the app should quit.
    fn on_key(&mut self, code: KeyCode) -> bool {
        if self.screen == Screen::MenuBar
            && matches!(code, KeyCode::Esc | KeyCode::Char('q') | KeyCode::Char('Q'))
        {
            return true;
        }

        match code {
            KeyCode::Esc => self.back(),
            KeyCode::Enter => self.activate(),
            KeyCode::Left => self.move_left(),
            KeyCode::Right | KeyCode::Tab => self.move_right(),
            KeyCode::Up => self.prev(),
            KeyCode::Down => self.next(),
            KeyCode::Backspace => self.edit(|v| {
                v.pop();
            }),
            KeyCode::Char(c) => self.edit(|v| v.push(c)),
            _ => {}
        }
        false
    }

    /// One step back from the current screen.
    fn back(&mut self) {
        self.screen = match self.screen {
            Screen::Output => self.returning_screen(),
            Screen::Form | Screen::Timezone => Screen::CommandList,
            Screen::CommandList => Screen::MenuBar,
            Screen::MenuBar => Screen::MenuBar,
        };
    }

    /// The screen the output view was opened from.
    fn returning_screen(&self) -> Screen {
        match self.panel {
            Panel::Generate | Panel::Validate | Panel::Completion => Screen::Form,
            Panel::Timezone => Screen::Timezone,
            Panel::Idle => Screen::MenuBar,
        }
    }

    fn activate(&mut self) {
        match self.screen {
            Screen::MenuBar => self.open_menu(),
            Screen::CommandList => self.run_command(),
            Screen::Form => self.submit_form(),
            Screen::Timezone => self.pick_timezone(),
            Screen::Output => self.screen = self.returning_screen(),
        }
    }

    /// Open the highlighted menu entry, loading its command list and form.
    fn open_menu(&mut self) {
        let (panel, item) = match self.menu_index {
            0 => (Panel::Generate, "Run generate"),
            1 => (Panel::Validate, "Run validate"),
            2 => (Panel::Completion, "Run completion"),
            3 => (Panel::Timezone, "Set timezone"),
            _ => return,
        };
        self.panel = panel;
        self.command_items = vec![item.to_string()];
        self.command_index = 0;

        match panel {
            Panel::Generate => self.load_generate_form(),
            Panel::Validate => self.load_validate_form(),
            Panel::Completion => self.load_completion_form(),
            Panel::Timezone => {
                self.tz = TimezoneState {
                    region: 0,
                    city: 0,
                    column: TzColumn::Region,
                    custom: String::new(),
                };
                self.cities = cities_for(0).iter().map(|s| s.to_string()).collect();
                self.screen = Screen::Timezone;
                return;
            }
            Panel::Idle => {}
        }
        self.screen = Screen::CommandList;
    }

    // ---- navigation -------------------------------------------------------

    fn prev(&mut self) {
        match self.screen {
            Screen::MenuBar => {
                self.menu_index = (self.menu_index + MENU.len() - 1) % MENU.len();
            }
            Screen::CommandList => {
                self.command_index = self.command_index.saturating_sub(1);
            }
            Screen::Form => {
                self.field_index = self.field_index.saturating_sub(1);
            }
            Screen::Timezone => match self.tz.column {
                TzColumn::Region => self.tz.region = self.tz.region.saturating_sub(1),
                TzColumn::City => self.tz.city = self.tz.city.saturating_sub(1),
            },
            Screen::Output => {}
        }
    }

    fn next(&mut self) {
        match self.screen {
            Screen::MenuBar => self.menu_index = (self.menu_index + 1) % MENU.len(),
            Screen::CommandList => {
                self.command_index = (self.command_index + 1) % self.command_items.len().max(1);
            }
            Screen::Form => {
                if !self.fields.is_empty() {
                    self.field_index = (self.field_index + 1) % self.fields.len();
                }
            }
            Screen::Timezone => match self.tz.column {
                TzColumn::Region => {
                    self.tz.region = (self.tz.region + 1) % self.regions.len();
                    self.sync_cities();
                }
                TzColumn::City => {
                    let len = self.cities.len().max(1);
                    self.tz.city = (self.tz.city + 1) % len;
                }
            },
            Screen::Output => {}
        }
    }

    fn move_left(&mut self) {
        match self.screen {
            Screen::MenuBar => self.prev(),
            Screen::Timezone if self.tz.column == TzColumn::City => {
                self.tz.column = TzColumn::Region;
            }
            _ => {}
        }
    }

    fn move_right(&mut self) {
        match self.screen {
            Screen::MenuBar => self.next(),
            // Only real regions have a city column to move into.
            Screen::Timezone
                if self.tz.column == TzColumn::Region
                    && self.tz.region < TIMEZONE_REGIONS.len() =>
            {
                self.tz.column = TzColumn::City;
            }
            _ => {}
        }
    }

    /// Recompute the city list after the region selection changed.
    fn sync_cities(&mut self) {
        self.cities = cities_for(self.tz.region)
            .iter()
            .map(|s| s.to_string())
            .collect();
        self.tz.city = 0;
        // "Custom…" has no city list, so keep focus on the region column to type.
        if self.tz.region >= TIMEZONE_REGIONS.len() {
            self.tz.column = TzColumn::Region;
        }
    }

    // ---- forms ------------------------------------------------------------

    fn load_generate_form(&mut self) {
        self.fields = vec![
            Field {
                label: "Config",
                value: self.config_path.clone().unwrap_or_default(),
                error: None,
            },
            Field {
                label: "Output dir",
                value: ".".to_string(),
                error: None,
            },
            Field {
                label: "Dry run",
                value: "false".to_string(),
                error: None,
            },
        ];
        self.field_index = 0;
    }

    fn load_validate_form(&mut self) {
        self.fields = vec![
            Field {
                label: "Config",
                value: self.config_path.clone().unwrap_or_default(),
                error: None,
            },
            Field {
                label: "Fix it",
                value: "false".to_string(),
                error: None,
            },
        ];
        self.field_index = 0;
    }

    fn load_completion_form(&mut self) {
        self.fields = vec![Field {
            label: "Shell",
            value: "bash".to_string(),
            error: None,
        }];
        self.field_index = 0;
    }

    /// Apply a character-level edit to the focused text field, clearing any
    /// stale validation error. A no-op when no text field is focused.
    fn edit(&mut self, f: impl FnOnce(&mut String)) {
        let value = match self.screen {
            Screen::Form => match self.fields.get_mut(self.field_index) {
                Some(field) => &mut field.value,
                None => return,
            },
            // The custom timezone entry is the only editable text in the picker.
            Screen::Timezone if self.tz.region >= TIMEZONE_REGIONS.len() => &mut self.tz.custom,
            _ => return,
        };
        f(value);
        if let Screen::Form = self.screen {
            self.fields[self.field_index].error = None;
        }
    }

    /// Run the active form's command, showing output or validation errors.
    fn submit_form(&mut self) {
        if let Some(err) = validate_form(self.panel, &self.fields) {
            if let Some(field) = self.fields.get_mut(self.field_index) {
                field.error = Some(err);
            }
            return;
        }

        let value = match self.fields.get(self.field_index) {
            Some(f) => f.value.trim().to_string(),
            None => return,
        };
        let label = self.fields[self.field_index].label;

        let result = match self.panel {
            Panel::Generate => {
                let output = self.fields[1].value.trim().to_string();
                let dry_run = parse_bool(&self.fields[2].value);
                cmd_generate(&value, Some(&output), dry_run)
            }
            Panel::Validate => cmd_validate(&value, parse_bool(&self.fields[1].value)),
            Panel::Completion => cmd_completion(&value),
            Panel::Timezone | Panel::Idle => return,
        };

        match result {
            Ok(text) => {
                self.output = format!("{}: {}\n\n{}", label, value, text);
                self.output_error = false;
            }
            Err(e) => {
                let msg = format!("{}: {}\n\n{}", label, value, e);
                self.toast(ToastKind::Error, first_line(&e.to_string()));
                self.output = msg;
                self.output_error = true;
            }
        }
        self.screen = Screen::Output;
    }

    // ---- timezone ---------------------------------------------------------

    /// Enter on the timezone picker: commit the selected zone to the config.
    fn pick_timezone(&mut self) {
        let Some(zone) = self.selected_zone() else {
            self.output = "Type an IANA timezone for the Custom… entry first.".to_string();
            self.output_error = true;
            self.screen = Screen::Output;
            return;
        };
        // `config_path` is always set; `App::new` substitutes a default.
        let path = self.config_path.clone().unwrap_or_default();

        match set_timezone(&path, &zone) {
            Ok(msg) => {
                self.output = format!("Timezone set to {}", zone);
                self.output_error = false;
                self.toast(ToastKind::Success, msg);
            }
            Err(e) => {
                self.output = format!("Failed to set timezone: {}", e);
                self.output_error = true;
            }
        }
        self.screen = Screen::Output;
    }

    /// The zone the picker currently points at, or None if it needs input.
    fn selected_zone(&self) -> Option<String> {
        if self.tz.region >= TIMEZONE_REGIONS.len() {
            let custom = self.tz.custom.trim();
            if custom.is_empty() {
                return None;
            }
            return Some(custom.to_string());
        }
        self.cities.get(self.tz.city).map(|s| s.to_string())
    }

    /// Execute the selected command-list entry.
    fn run_command(&mut self) {
        match self.panel {
            Panel::Generate | Panel::Validate | Panel::Completion => self.submit_form(),
            Panel::Timezone => self.screen = Screen::Timezone,
            Panel::Idle => {}
        }
    }

    // ---- toast ------------------------------------------------------------

    fn toast(&mut self, kind: ToastKind, message: impl Into<String>) {
        self.toast = Some(Toast {
            message: message.into(),
            kind,
            raised_at: Instant::now(),
        });
    }

    fn expire_toast(&mut self) {
        if let Some(t) = &self.toast {
            if t.raised_at.elapsed() >= TOAST_TTL {
                self.toast = None;
            }
        }
    }

    // ---- rendering --------------------------------------------------------

    fn draw(&mut self, f: &mut Frame) {
        let rows = Layout::default()
            .direction(Direction::Vertical)
            .constraints([
                Constraint::Length(1),
                Constraint::Min(0),
                Constraint::Length(1),
            ])
            .split(f.size());

        draw_menu_bar(f, rows[0], self.menu_index);
        self.draw_body(f, rows[1]);
        draw_status(f, rows[2], self.screen);

        if let Some(t) = &self.toast {
            draw_toast(f, t);
        }
    }

    fn draw_body(&mut self, f: &mut Frame, area: Rect) {
        let cols = Layout::default()
            .direction(Direction::Horizontal)
            .constraints([Constraint::Length(24), Constraint::Min(0)])
            .split(area);

        let rows: Vec<ListItem> = self
            .command_items
            .iter()
            .enumerate()
            .map(|(i, item)| {
                let style = if i == self.command_index {
                    Style::default().fg(Color::Black).bg(Color::Blue)
                } else {
                    Style::default().fg(Color::White)
                };
                ListItem::new(item.as_str()).style(style)
            })
            .collect();
        f.render_stateful_widget(
            List::new(rows).block(Block::default().borders(Borders::ALL).title("Commands")),
            cols[0],
            &mut select((!self.command_items.is_empty()).then_some(self.command_index)),
        );

        match self.screen {
            Screen::Output => draw_output(f, cols[1], &self.output, self.output_error),
            Screen::Timezone => self.draw_timezone(f, cols[1]),
            _ => self.draw_form(f, cols[1]),
        }
    }

    /// Draw the active form, or a hint when nothing is selected.
    fn draw_form(&self, f: &mut Frame, area: Rect) {
        let title = match self.panel {
            Panel::Generate => "Generate",
            Panel::Validate => "Validate",
            Panel::Completion => "Completion",
            Panel::Timezone | Panel::Idle => "Action",
        };

        if self.fields.is_empty() {
            f.render_widget(
                Paragraph::new("Select a menu entry with ←/→, then Enter.")
                    .block(Block::default().borders(Borders::ALL).title(title))
                    .wrap(Wrap { trim: true }),
                area,
            );
            return;
        }

        let mut lines = Vec::new();
        for (i, field) in self.fields.iter().enumerate() {
            let focused = i == self.field_index;
            let marker = if focused { "▶" } else { " " };
            lines.push(Line::from(vec![
                Span::raw(format!("{} ", marker)),
                Span::styled(
                    field.label.to_string(),
                    Style::default().fg(if focused { Color::Yellow } else { Color::Gray }),
                ),
            ]));
            let value_style = Style::default().fg(if field.error.is_some() {
                Color::Red
            } else {
                Color::White
            });
            lines.push(Line::from(vec![Span::styled(
                format!("  {}", field.value),
                value_style,
            )]));
            if let Some(err) = &field.error {
                lines.push(Line::from(Span::styled(
                    format!("  ✗ {}", err),
                    Style::default().fg(Color::Red),
                )));
            }
        }
        lines.push(Line::from(Span::styled(
            "Enter run · Esc back",
            Style::default().fg(Color::DarkGray),
        )));

        f.render_widget(
            Paragraph::new(lines)
                .block(Block::default().borders(Borders::ALL).title(title))
                .wrap(Wrap { trim: true }),
            area,
        );
    }

    /// Two-column region/city picker.
    fn draw_timezone(&self, f: &mut Frame, area: Rect) {
        let cols = Layout::default()
            .direction(Direction::Horizontal)
            .constraints([Constraint::Percentage(40), Constraint::Percentage(60)])
            .split(area);

        let region_focused = self.tz.column == TzColumn::Region;
        let region_highlight = region_focused.then_some(self.tz.region);
        f.render_stateful_widget(
            column("Region", &self.regions, region_highlight, region_focused),
            cols[0],
            &mut select(region_highlight),
        );

        // The custom entry types a zone rather than choosing from a list.
        if self.tz.region >= TIMEZONE_REGIONS.len() {
            let shown = if region_focused {
                format!("{}▌", self.tz.custom)
            } else {
                self.tz.custom.clone()
            };
            let border = if region_focused {
                Color::Yellow
            } else {
                Color::DarkGray
            };
            f.render_widget(
                Paragraph::new(Span::styled(shown, Style::default().fg(Color::White))).block(
                    Block::default()
                        .borders(Borders::ALL)
                        .title("IANA timezone")
                        .border_style(Style::default().fg(border)),
                ),
                cols[1],
            );
            return;
        }

        let city_focused = self.tz.column == TzColumn::City;
        let city_highlight = city_focused.then_some(self.tz.city);
        f.render_stateful_widget(
            column("City", &self.cities, city_highlight, city_focused),
            cols[1],
            &mut select(city_highlight),
        );
    }
}

/// Draw the top menu bar with `active` highlighted.
fn draw_menu_bar(f: &mut Frame, area: Rect, active: usize) {
    let spans: Vec<Span> = MENU
        .iter()
        .enumerate()
        .flat_map(|(i, label)| {
            let style = if i == active {
                Style::default()
                    .fg(Color::Black)
                    .bg(Color::Blue)
                    .add_modifier(Modifier::BOLD)
            } else {
                Style::default().fg(Color::Gray)
            };
            [Span::styled(format!(" {} ", label), style), Span::raw(" ")]
        })
        .collect();
    f.render_widget(Paragraph::new(Line::from(spans)), area);
}

/// Draw the bottom key-hint bar for `screen`.
fn draw_status(f: &mut Frame, area: Rect, screen: Screen) {
    let help = match screen {
        Screen::MenuBar => "←/→ menu · Enter open · q quit",
        Screen::CommandList => "↑/↓ select · Enter run · Esc menu",
        Screen::Form => "↑/↓ field · type to edit · Enter run · Esc back",
        Screen::Timezone => "↑/↓ move · ←→ column · Enter pick · Esc back",
        Screen::Output => "Enter back · Esc back",
    };
    f.render_widget(
        Paragraph::new(help).style(Style::default().fg(Color::DarkGray)),
        area,
    );
}

/// Build a bordered list column, highlighting `highlight` when the column has focus.
/// The list borrows `items`, so both share one lifetime.
fn column<'a>(
    title: &'a str,
    items: &'a [String],
    highlight: Option<usize>,
    focused: bool,
) -> List<'a> {
    let rows = items.iter().enumerate().map(|(i, item)| {
        let style = match (highlight, focused) {
            (Some(h), _) if h == i => Style::default().fg(Color::Black).bg(Color::Blue),
            (Some(_), true) => Style::default().fg(Color::Cyan),
            _ => Style::default().fg(Color::White),
        };
        ListItem::new(item.as_str()).style(style)
    });
    let border = if focused {
        Color::Yellow
    } else {
        Color::DarkGray
    };
    List::new(rows.collect::<Vec<_>>())
        .block(
            Block::default()
                .borders(Borders::ALL)
                .title(title)
                .border_style(Style::default().fg(border)),
        )
        .highlight_symbol("> ")
}

/// A `ListState` with a single optional selection.
fn select(index: Option<usize>) -> ListState {
    let mut state = ListState::default();
    state.select(index);
    state
}

/// Draw the command output pane.
fn draw_output(f: &mut Frame, area: Rect, output: &str, is_error: bool) {
    let border = if is_error { Color::Red } else { Color::Green };
    let title = if is_error {
        "Output (failed)"
    } else {
        "Output"
    };
    f.render_widget(
        Paragraph::new(output.to_string())
            .block(
                Block::default()
                    .borders(Borders::ALL)
                    .title(title)
                    .border_style(Style::default().fg(border)),
            )
            .wrap(Wrap { trim: false }),
        area,
    );
}

/// Draw a transient message over the center of the screen.
fn draw_toast(f: &mut Frame, toast: &Toast) {
    let bg = match toast.kind {
        ToastKind::Success => Color::Green,
        ToastKind::Error => Color::Red,
    };
    let area = centered(70, 12, f.size());
    f.render_widget(Clear, area);
    f.render_widget(
        Paragraph::new(toast.message.clone())
            .style(Style::default().fg(Color::Black).bg(bg))
            .wrap(Wrap { trim: true })
            .alignment(Alignment::Center),
        area,
    );
}

/// A rect of the given percentage size, centered in `r`.
fn centered(pct_x: u16, pct_y: u16, r: Rect) -> Rect {
    let rows = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Percentage((100 - pct_y) / 2),
            Constraint::Percentage(pct_y),
            Constraint::Percentage((100 - pct_y) / 2),
        ])
        .split(r);
    Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Percentage((100 - pct_x) / 2),
            Constraint::Percentage(pct_x),
            Constraint::Percentage((100 - pct_x) / 2),
        ])
        .split(rows[1])[1]
}

/// The first line of `text`, trimmed — toasts are one-liners.
fn first_line(text: &str) -> String {
    text.lines().next().unwrap_or(text).trim().to_string()
}

/// Timezones belonging to `region`, or empty for the "Custom…" entry.
fn cities_for(region: usize) -> Vec<&'static str> {
    let Some(name) = TIMEZONE_REGIONS.get(region) else {
        return Vec::new();
    };
    COMMON_TIMEZONES
        .iter()
        .copied()
        .filter(|tz| tz.starts_with(&format!("{}/", name)))
        .collect()
}

/// Parse a form boolean. Anything other than a recognized true value is false.
fn parse_bool(value: &str) -> bool {
    matches!(
        value.trim().to_ascii_lowercase().as_str(),
        "true" | "yes" | "y" | "1"
    )
}

/// Validate the form for `panel`, returning the first error or None if valid.
fn validate_form(panel: Panel, fields: &[Field]) -> Option<String> {
    let path = fields.first()?.value.trim().to_string();

    if panel == Panel::Completion {
        let shell = path.to_ascii_lowercase();
        if !SHELLS.contains(&shell.as_str()) {
            return Some(format!(
                "unsupported shell: {} (want one of {})",
                path,
                SHELLS.join(", ")
            ));
        }
        return None;
    }

    if path.is_empty() {
        return Some("config path is required".to_string());
    }
    if !Path::new(&path).exists() {
        return Some(format!("no such file: {}", path));
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    fn field(label: &'static str, value: &str) -> Field {
        Field {
            label,
            value: value.to_string(),
            error: None,
        }
    }

    #[test]
    fn typing_and_backspace_edit_the_focused_field_only() {
        let mut app = App::new(None);
        app.screen = Screen::Form;
        app.fields = vec![field("Config", ""), field("Dry run", "false")];

        app.on_key(KeyCode::Char('a'));
        app.on_key(KeyCode::Char('b'));
        assert_eq!(app.fields[0].value, "ab");
        assert_eq!(app.fields[1].value, "false");

        app.on_key(KeyCode::Backspace);
        assert_eq!(app.fields[0].value, "a");
    }

    #[test]
    fn editing_clears_a_previous_validation_error() {
        let mut app = App::new(None);
        app.screen = Screen::Form;
        app.fields = vec![field("Shell", "tcsh")];
        app.fields[0].error = Some("unsupported shell".to_string());

        app.on_key(KeyCode::Char('h'));
        assert_eq!(app.fields[0].error, None);
    }

    #[test]
    fn completion_form_rejects_unknown_shell() {
        let err = validate_form(Panel::Completion, &[field("Shell", "tcsh")])
            .expect("tcsh should be rejected");
        assert!(err.contains("unsupported shell"), "{}", err);
    }

    #[test]
    fn completion_form_accepts_every_supported_shell() {
        for shell in SHELLS {
            assert!(
                validate_form(Panel::Completion, &[field("Shell", shell)]).is_none(),
                "{} rejected",
                shell
            );
        }
    }

    #[test]
    fn config_path_must_exist() {
        let missing = [
            field("Config", "/nonexistent/cloudseed.toml"),
            field("Dry run", "false"),
        ];
        let err = validate_form(Panel::Generate, &missing).expect("missing file rejected");
        assert!(err.contains("no such file"), "{}", err);

        // Use the source file's own path, resolved from the crate root that
        // `cargo test` sets as the working directory.
        let self_path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../..")
            .join(file!());
        let present = [
            field("Config", self_path.to_str().unwrap()),
            field("Dry run", "false"),
        ];
        assert!(validate_form(Panel::Generate, &present).is_none());
    }

    #[test]
    fn empty_config_path_is_rejected() {
        let fields = [field("Config", "   "), field("Fix it", "false")];
        let err = validate_form(Panel::Validate, &fields).expect("blank path rejected");
        assert!(err.contains("required"), "{}", err);
    }

    #[test]
    fn parse_bool_only_accepts_true_like_values() {
        assert!(parse_bool("true"));
        assert!(parse_bool("YES"));
        assert!(parse_bool("1"));
        assert!(!parse_bool("false"));
        assert!(!parse_bool(""));
        assert!(!parse_bool("maybe"));
    }

    #[test]
    fn cities_are_filtered_to_their_region() {
        let europe = cities_for(
            TIMEZONE_REGIONS
                .iter()
                .position(|r| *r == "Europe")
                .unwrap(),
        );
        assert!(europe.iter().all(|tz| tz.starts_with("Europe/")));
        assert!(europe.contains(&"Europe/London"));

        // The trailing "Custom…" entry has no index in TIMEZONE_REGIONS.
        assert!(cities_for(TIMEZONE_REGIONS.len()).is_empty());
    }

    #[test]
    fn selected_zone_follows_region_and_city() {
        let mut app = App::new(None);
        let london = TIMEZONE_REGIONS
            .iter()
            .position(|r| *r == "Europe")
            .unwrap();

        app.tz.region = london;
        app.cities = cities_for(london).iter().map(|s| s.to_string()).collect();
        app.tz.city = 0;
        assert_eq!(app.selected_zone().as_deref(), Some("Europe/London"));

        // The custom region needs typed input.
        app.tz.region = TIMEZONE_REGIONS.len();
        assert_eq!(app.selected_zone(), None);
        app.tz.custom = "Mars/Olympus".to_string();
        assert_eq!(app.selected_zone().as_deref(), Some("Mars/Olympus"));
    }

    #[test]
    fn moving_past_the_last_region_wraps_and_resyncs_cities() {
        let mut app = App::new(None);
        app.screen = Screen::Timezone;
        app.tz.region = TIMEZONE_REGIONS.len() - 1; // Pacific
        app.on_key(KeyCode::Down);

        assert_eq!(app.tz.region, TIMEZONE_REGIONS.len()); // Custom…
        assert!(app.cities.is_empty());
        // Custom has no city column, so focus stays put.
        assert_eq!(app.tz.column, TzColumn::Region);
    }

    #[test]
    fn menu_bar_quit_keys_only_apply_on_the_menu_bar() {
        let mut app = App::new(None);
        assert!(app.on_key(KeyCode::Char('q')));

        app.screen = Screen::Form;
        app.fields = vec![field("Shell", "")];
        assert!(!app.on_key(KeyCode::Char('q')));
        // 'q' is typed into the field instead.
        assert_eq!(app.fields[0].value, "q");
    }
}
