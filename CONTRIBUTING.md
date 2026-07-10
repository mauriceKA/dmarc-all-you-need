# Contributing

Contributions are welcome — bug reports, fixes, features, docs. Please read
the **Licensing of contributions** section below before opening a pull
request; this project is dual-licensed and asks for your explicit consent.

## Development setup

```sh
# backend
python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
pytest                       # tests must pass
ruff check backend tests     # lint must be clean

# frontend
cd frontend
npm ci
npm run dev                  # dev server, proxies /api to 127.0.0.1:8080
npx tsc -b && npm run build  # must type-check and build
```

## Guidelines

- **Dependency budget.** The backend deliberately has 3 runtime
  dependencies and the frontend a handful. PRs adding a dependency need a
  strong justification — "it saves 30 lines" is not one.
- **Untrusted input stays guarded.** Report attachments and their XML are
  attacker-controlled: keep `defusedxml`, size caps, and stream
  decompression intact, and add a malicious-input test fixture when you
  touch the parser.
- Add or update tests for behavior changes; keep `pytest` and `ruff` green.
- Match the style of the surrounding code; small focused PRs review faster.

## Licensing of contributions

This project is available under the AGPL-3.0-or-later **and** under
commercial licenses sold by the copyright holder (see
[README — License](README.md#license)). To keep that dual-licensing model
possible, every contribution needs two things from you, both expressed by
adding a `Signed-off-by` line to your commits (`git commit -s`):

### 1. Developer Certificate of Origin

You certify the [Developer Certificate of Origin 1.1](https://developercertificate.org/)
— in short: the contribution is your own work (or you have the right to
submit it) and you are entitled to license it as stated below.

### 2. License grant (dual-licensing consent)

Modeled on the [Harmony Individual Contributor License Agreement](https://harmonyagreements.org/):

> You retain the copyright in your contribution. You grant Patrik Spieß a
> perpetual, worldwide, non-exclusive, transferable, royalty-free,
> irrevocable copyright license to use, reproduce, modify, display,
> distribute, and sublicense your contribution, **including the right to
> license it under terms other than the AGPL** (such as commercial
> licenses).
>
> In return, the maintainer promises: **every accepted contribution will
> always also remain available under the AGPL-3.0-or-later** (or a later
> version of the same license family). The free version of this project
> will not be withdrawn.

Plainly said, with no surprises hidden: you keep your copyright and can do
anything you like with your own code elsewhere; the project stays free
software forever; and the maintainer — alone — may additionally sell
license exceptions that cover your contribution. If you are not comfortable
with that last part, that is entirely legitimate — but please don't submit
code to this repository, since we cannot merge AGPL-only contributions
without breaking the licensing model.

### How to sign

```sh
git commit -s -m "Fix zip member size check"
```

which adds:

```
Signed-off-by: Your Name <your@email.example>
```

Use your real name and a reachable email address. By signing off you agree
to both sections above for that contribution.
