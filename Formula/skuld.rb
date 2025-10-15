class Skuld < Formula
  desc "Skuld: WakaTime + Git → Jira worklogs"
  homepage "https://github.com/imprisonedmind/skuld"
  head "https://github.com/imprisonedmind/skuld.git", branch: "main"

  depends_on "python@3.11"

  def install
    libexec.install Dir["skuld", "docs", ".skuld.yaml.example", "README.md"]
    (bin/"skuld").write <<~EOS
      #!/bin/bash
      export PYTHONPATH="#{libexec}"
      exec "#{Formula["python@3.11"].opt_bin}/python3" -m skuld.cli "$@"
    EOS
    (bin/"skuld").chmod 0755
  end

  test do
    system "#{bin}/skuld", "sync", "today", "--test"
  end
end

