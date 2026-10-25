# Team 058 — final GitHub submission steps

**Only the contents committed to `openegiz-contest/team-058` on the `main` branch by October 25, 2026, 23:59 Astana time count. Uploading a ZIP as one GitHub file is NOT the same as uploading the repository contents.**

## Before committing

1. In `SUBMISSION.md`, replace `REPLACE_WITH_REGISTERED_GITHUB_USERNAME` with **your exact contest-registered GitHub login**. We have not been given that login, so this field intentionally remains to prevent inventing one.
2. Check that `README.md`, `SUBMISSION.md`, and `presentation.pdf` are all at the repository **root**.
3. Check the `.env` file is **not** committed; clean startup generates it on the target VM.
4. Do **not** run any `docker compose down -v`, `git push --force` or volume removal during submission.

## Upload (from Ubuntu WSL, adjust ZIP name/path if necessary)

```bash
cd ~
git clone https://github.com/openegiz-contest/team-058.git
cd team-058
unzip -oq /mnt/c/Users/dzzen/Downloads/OreFlow_KZ_Team058_GitHub_Final_20261025.zip -d .
# EDIT SUBMISSION.md: replace the GitHub username placeholder with your registered login.
git status --short
git add -A
git commit -m "Submit OreFlow KZ 2.3 digital mine, evidence and presentation"
git push origin main
```

If the repo is already cloned, use that checkout instead of cloning a second time. Review existing uncommitted changes before unzipping. When commit finishes, verify on GitHub that the root has `README.md`, `SUBMISSION.md` and `presentation.pdf` and that the latest commit is on `main`.

## Quick functional validation

On a clean Ubuntu 24.04 machine with Docker Engine and Compose v2:

```bash
bash scripts/oreflow-start.sh
bash scripts/oreflow-verify-ready.sh
```

Then open http://localhost:8099. The presentation screenshots were captured from the frontend using simulated API data; run your live stack for an independent evidence check.
