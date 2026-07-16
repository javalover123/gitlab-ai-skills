# General Writing Guidelines

This reference covers every writing context that doesn't have its own dedicated file. Emails, messages, changelog entries, technical specs, proposals, design docs, chat messages, wiki pages -- if you're writing something and it's not a code comment, MR description, commit message, issue, or long-form documentation, you're in the right place.

You can also treat this as a standalone summary of the core principles. The other reference files go deeper into their specific domains, but if you only load one file, this one gives you enough to write well.

## Core principles

Active voice. Direct statements. No hedging unless you're genuinely uncertain about something specific. "The parser rejects malformed input" beats "The input may potentially be rejected by the parser in certain scenarios."

Contractions aren't optional. Write "don't" instead of "do not," "it's" instead of "it is," "you'll" instead of "you will," "won't" instead of "will not." The only exception is when the formal form adds emphasis: "Do *not* run this in production" lands harder than "Don't run this in production."

One idea per sentence. Target an average under 25 words, but vary deliberately. Some sentences hit hard in four words. Others meander through a thought, connecting context and consequence before arriving at the point. That variance is what sounds human. Monotonous rhythm -- every sentence roughly the same length, roughly the same structure -- is one of the strongest AI tells.

Tense matters. Present tense for current behaviour: "The scheduler runs every 5 minutes." Past tense for changes: "We removed the polling interval." Future tense for planned work: "The next release will include date filtering."

Every sentence earns its place by introducing new information. If you catch yourself restating something you already said in slightly different words, delete it. Repetition dressed as reinforcement is filler.

Oxford comma, always: "logs, metrics, and traces." Sentence case for headings: "Core principles" not "Core Principles."

Write like a knowledgeable, friendly colleague -- someone who's genuinely enthusiastic about clever solutions but doesn't perform enthusiasm. "This is neat" beats "this provides significant value." Show warmth through specificity: acknowledging what's tricky, offering concrete help, referencing shared context. Not through exclamation cascades or generic friendliness.

Directness is respect. It signals you value the reader's time. Be a little playful where it fits. Technical writing doesn't have to be dry. But never let personality undermine precision.

## Email and message writing

Lead with your point. The first sentence should contain your ask, your answer, or the information you're conveying. Context comes after, not before.

Don't bury the important thing under two paragraphs of pleasantries or background. Your reader is scanning, probably on a phone, probably between other things. If the key information is in paragraph three, they might not get there.

One email, one topic. The moment you type "also" to introduce a completely different subject, stop. That's a separate message. Mixing topics guarantees one of them gets lost in the reply thread.

For requests, make the action clear. Who needs to do what, by when? "Can you review the migration script before Thursday's deploy?" is actionable. "It'd be great if someone could take a look at some point" is not.

Keep context proportional. A quick question needs a sentence of background, not a page. A complex proposal might need a few paragraphs. Match the weight of the context to the weight of the ask.

Reply inline when addressing multiple points from a previous message. It's easier for both of you to track which question got which answer. Don't make people guess which of their four questions your single-paragraph reply is addressing.

## Changelog entries

Write in past tense. These describe what already shipped, not what you're planning to do.

Group entries by type:

- **Added** -- new features or capabilities
- **Changed** -- modifications to existing behaviour
- **Fixed** -- bug fixes
- **Removed** -- features or options that no longer exist
- **Deprecated** -- features still present but scheduled for removal
- **Security** -- vulnerability fixes or security-related changes

Each entry is one sentence. State what changed and why it matters to the person reading it. They don't care about file names or implementation details -- they care about what's different from their perspective.

**Good entries:**

- Added date range filtering to the audit log endpoint, so you can search events by time period instead of scrolling the full list.
- Fixed a bug where jobs were silently dropped after three retry failures instead of moving to the dead letter queue.
- Removed the deprecated `poll_interval` config option. Use `watch_timeout` instead.
- Changed the default connection pool size from 4 to 10 to better match typical production workloads.

**Bad entries:**

- Updated worker_pool.go to fix error handling. *(What was wrong? What's different now?)*
- Added new feature. *(Which feature?)*
- Various bug fixes and improvements. *(This tells the reader literally nothing.)*

## Technical specifications

Precision is the priority. Define terms on first use -- don't assume everyone reading the spec shares your vocabulary. "The arbiter (the component that resolves conflicting write requests)" takes one extra clause and prevents a whole category of misunderstanding.

Concrete examples beat abstract descriptions every time. If you're specifying an API, show request and response bodies. If you're describing a data format, include a sample document. If you're defining behaviour, walk through a scenario.

Distinguish requirements from recommendations from optional behaviour. Use RFC 2119 language intentionally:

- **Must / shall** -- non-negotiable requirements
- **Should** -- recommended defaults that can be overridden with good reason
- **May** -- genuinely optional behaviour

Don't scatter these carelessly. Every "must" creates a compliance obligation. Every "should" implies someone might reasonably do otherwise. If you mean "must," say "must."

Keep sections focused on one concern. A section about authentication shouldn't drift into rate limiting. A section about data format shouldn't wander into deployment topology. If two concerns interact, write each one in its own section and cross-reference.

Specs don't need to be dry to be precise. You can write "The retry delay doubles after each failure, capping at 30 seconds -- so attempts happen at 1s, 2s, 4s, 8s, 16s, 30s, 30s..." and that's both precise and readable. Personality and precision coexist just fine.

Version your specs. Date them. Note who authored them. When a spec changes, note what changed and why. Six months from now, someone will need to understand not just what the spec says, but what it used to say and why it evolved.

## Proposals and design documents

Start with the problem, not the solution. Before you pitch your approach, make sure the reader understands what's broken or missing. One paragraph is usually enough.

State your proposed solution clearly and early. Don't build suspense. The reader should know your recommendation by the end of the second section, then spend the rest of the document understanding why.

Address alternatives you considered. This isn't ceremony -- it's proof that you thought it through. "We considered X but rejected it because Y" builds more confidence than a proposal that pretends no other options exist.

Be honest about tradeoffs. Every design decision has costs. Name them. "This approach adds ~200ms latency to the write path, which we consider acceptable given the consistency guarantee it provides" is more trustworthy than a proposal that only talks about benefits.

End with next steps, not a summary. What happens if this gets approved? Who does what? What's the timeline? Give the reader a path forward.

## Banned patterns (quick reference)

Never use: delve, utilize, leverage, streamline, facilitate, robust, comprehensive, seamless, innovative, cutting-edge, holistic, synergy, paradigm, ecosystem, stakeholder, empower, foster, pivotal, endeavour. <!-- voice-ok -->

Never use: "it is important to note," "in order to," "at the end of the day," "moving forward," "it should be noted that," "plays a crucial role," "in the realm of." <!-- voice-ok -->

Never start conclusions with "In conclusion," "Overall," "In summary," "To summarize," or "Ultimately." <!-- voice-ok -->

Never list exactly 3 or 5 items. Use 2, 4, 6, or 7 -- or rewrite as prose.

Vary sentence lengths, paragraph openings, and internal structure between sections. Monotony is the tell.

Full list with alternatives and examples: see `banned-patterns.md`.

## Warmth and competence (quick reference)

Substantive warmth -- specificity, helpfulness, acknowledging context -- builds trust and credibility. Decorative warmth -- generic friendliness, emoji cascades, enthusiasm stacking -- can undermine perceived competence.

Emoji: 0-2 in informal contexts (chat, celebratory messages). Zero in anything formal or technical.

Maximum one exclamation point per piece of writing. Use it for genuine acknowledgment, never on technical claims.

Hedge only when genuinely uncertain, and be specific about what you're uncertain about. "I haven't tested this on ARM, so the alignment behaviour might differ" is good. "This could potentially maybe cause issues" is not.

Full guidelines with research context and detailed examples: see `warmth-competence.md`.
