# Contributing
Ideas and fixes are welcome.
1. Fork the repo and make your change in `index.html` (it is one self-contained file).
2. Do not edit `hero-background.html`; it is the animated backdrop. Its video is 960x540 on purpose: the page converts one video frame per tick, so a small source keeps the home page smooth.
3. Run the smoke test: `pip install playwright && playwright install chromium && python tests/smoke.py`
4. Open a pull request describing what changed and why.
