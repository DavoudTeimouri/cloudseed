class Cloudseed < Formula
  desc "CloudSeed - Generate cloud-init / Cloudbase-Init VM templates for vSphere and KVM (Linux + Windows). Zero dependencies (stdlib only)."
  homepage "https://github.com/DavoudTeimouri/cloudseed"
  url "https://github.com/DavoudTeimouri/cloudseed/archive/refs/tags/v2.0.2.tar.gz"
  sha256 "REPLACE_WITH_ACTUAL_SHA256"
  license "MIT"
  head "https://github.com/DavoudTeimouri/cloudseed.git", branch: "main"

  depends_on "python@3.12"

  def install
    # Install as a Python package
    system "pip3", "install", "--prefix=#{libexec}", "."
    bin.install_symlink libexec/"bin/cloudseed"
  end

  test do
    system "#{bin}/cloudseed", "--version"
    system "#{bin}/cloudseed", "--detect-cloud-init"
  end
end
