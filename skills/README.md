# QuotaCompass agent skills

Both packages are generated from `shared/BODY.md` and the stdlib-only `shared/scripts/query.py` so behavior cannot drift between Hermes and OpenClaw.

Run `python skills/build_skills.py` after editing shared content or frontmatter. Install the generated directory locally before publishing:

- Hermes: copy `skills/hermes/quotacompass` into a configured skill root, then test with `hermes --toolsets skills,terminal --skills quotacompass --oneshot "How are my AI quotas looking?"`. The generated frontmatter declares the required `terminal` toolset and invokes its helper through `${HERMES_SKILL_DIR}`.
- OpenClaw: `openclaw skills install ./skills/openclaw/quotacompass`, then verify the `quotacompass` slash command/skill.

Registry publication is deliberately a human release action because it requires choosing the final repository owner, authenticating, and accepting public distribution.
