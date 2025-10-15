Public Homebrew Tap (imprisonedmind/homebrew-skuld)

Goal: `brew tap imprisonedmind/skuld` then `brew install skuld` for a stable release.

1) Tag a release
- In this repo:
  - `git tag v0.1.1`
  - `git push origin v0.1.1`

2) Compute the release tarball checksum
- On your machine:
  - `curl -L -o skuld-0.1.1.tar.gz https://github.com/imprisonedmind/skuld/archive/refs/tags/v0.1.1.tar.gz`
  - `shasum -a 256 skuld-0.1.1.tar.gz | cut -d' ' -f1` → copy the SHA256

3) Create the tap repo
- Create a new public repo: `imprisonedmind/homebrew-skuld`
- Add this file at `Formula/skuld.rb` (use your tag + sha):

```
class Skuld < Formula
  desc "Skuld: WakaTime + Git → Jira worklogs"
  homepage "https://github.com/imprisonedmind/skuld"
  url "https://github.com/imprisonedmind/skuld/archive/refs/tags/v0.1.1.tar.gz"
  sha256 "<RELEASE_TARBALL_SHA256>"
  license :cannot_represent

  head "https://github.com/imprisonedmind/skuld.git", branch: "main"

  depends_on "python"

  def install
    libexec.install Dir["skuld", "docs", ".skuld.yaml.example", "README.md", "LICENSE"]
    (bin/"skuld").write <<~EOS
      #!/bin/bash
      export PYTHONPATH="#{libexec}"
      exec "#{Formula["python"].opt_bin}/python3" -m skuld.cli "$@"
    EOS
    (bin/"skuld").chmod 0755
  end

  test do
    system "#{bin}/skuld", "sync", "today", "--test"
  end
end
```

4) Users install from the tap
- `brew tap imprisonedmind/skuld`
- `brew install skuld`

Updating
- Tag a new version (e.g., v0.1.1), update `url` + `sha256` in the tap formula, push.
- Users can `brew upgrade skuld`.

Notes
- `license :cannot_represent` is acceptable in a tap for a proprietary license (see this repo’s LICENSE). For Homebrew/core, an OSI-approved license is required.
- Keep the test non‑network and deterministic (we call `sync today --test`).
