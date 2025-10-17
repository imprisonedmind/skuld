# NOTE: This file is a development scaffold/example and is not used by Homebrew.
# The actual tap formula lives in the separate repo `imprisonedmind/homebrew-skuld`
# which Homebrew uses via: `brew tap imprisonedmind/skuld`.

class Skuld < Formula
  desc "Skuld: WakaTime + Git → Jira worklogs"
  homepage "https://github.com/imprisonedmind/skuld"
  head "https://github.com/imprisonedmind/skuld.git", branch: "main"
  license "mit"

  depends_on "python"

  def install
    libexec.install Dir["skuld", "docs", ".skuld.yaml.example", "README.md"]
    (bin/"skuld").write <<~EOS
      #!/bin/bash
      export PYTHONPATH="#{libexec}"
      exec "#{Formula["python"].opt_bin}/python3" -m skuld.cli "$@"
    EOS
    (bin/"skuld").chmod 0755
  end

  test do
    system "#{bin}/skuld", "--help"
  end
end
