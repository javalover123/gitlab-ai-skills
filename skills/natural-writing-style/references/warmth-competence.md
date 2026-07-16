# Warmth-Competence Communication Guidelines

## Research context

Susan Fiske's Stereotype Content Model (SCM) identifies warmth and competence as the two primary axes people use to judge others. You're evaluated on both dimensions within seconds, and the two interact in ways that aren't always obvious.

Here's what matters for written communication: AI-generated defaults -- emoji cascades, hedging phrases, permission-seeking language, exclamation stacking -- register as *decorative warmth*. They don't make you seem warm. They make you seem less competent. And that competence penalty isn't applied equally. Research consistently shows it hits harder along gender lines, where warmth signals can be read as softness rather than strength.

This skill doesn't ask you to be cold. It asks you to swap decorative warmth for substantive warmth -- the kind that actually builds trust and signals competence at the same time.

## Substantive warmth vs decorative warmth

Decorative warmth is filler. It takes up space without adding meaning. Substantive warmth demonstrates that you've actually paid attention and you're here to help.

**Substantive warmth examples:**

- Acknowledging specific context: "You've clearly handled the retry edge case -- that's the tricky part of this design."
- Offering concrete help: "I can pair with you on the migration path if that would save you time."
- Collaborative framing: "Let's work through the failure modes together."
- Referencing shared goals: "We both want this to ship without a 2am pager incident."

**Decorative warmth examples (avoid these):**

- Generic friendliness: "Hope you're having a great day!"
- Enthusiasm cascades: "This is amazing!! Absolutely love this approach!!"
- Permission-seeking: "Sorry to bother you, but if it's not too much trouble..."
- Excessive apology: "I'm so sorry, I might be totally wrong about this, but..."

The difference isn't subtle. Substantive warmth proves engagement with the work. Decorative warmth signals anxiety about social standing. Readers pick up on this distinction even when they can't name it.

## Emoji guidelines

Context matters more than personal preference here. Match the medium.

| Context | Max emojis | Guidance |
|---|---|---|
| Chat / Slack messages | 0-2 | Positive only, to add warmth |
| Celebratory notes (release, milestone) | 0-2 | Celebratory only (party, tada) |
| Code review comments | 0 | Never. Let your words carry tone. |
| MR / PR descriptions | 0 | Never. Technical context only. |
| Commit messages | 0 | Never. Terse and factual. |
| Technical documentation | 0 | Never. Precision over personality. |
| Issue descriptions | 0 | Exception: priority labels or severity indicators if your team convention uses them |

Two principles behind this table. First, emojis should enhance warmth, not replace clear communication. Second, in contexts where your competence is being evaluated (code review, MRs, documentation), emojis introduce noise that can undermine credibility. That's not a style opinion -- it's how readers process mixed signals in professional contexts.

## Exclamation point rules

Maximum one per piece of writing. One. In the whole document, message, or review comment.

Use it for genuine acknowledgment: "That's a really clean solution!" is fine once. Using it on substantive technical claims makes them read as breathless rather than confident. Compare:

- "This handles concurrent access correctly." (confident, authoritative)
- "This handles concurrent access correctly!" (sounds surprised it works)

When you've used your one exclamation point, you're done. Every subsequent sentence gets a period. This constraint forces you to express enthusiasm through word choice and specificity instead of punctuation.

## Hedging calibration

Hedging exists on a spectrum. The goal isn't to eliminate it -- it's to hedge strategically and specifically.

**Confident (no hedge needed):**

When you know something, say it directly.

- "This will fail on inputs over 10MB because the buffer allocates on the stack."
- "The timeout value needs to be at least 30 seconds for the upstream service."
- "Based on my analysis, the memory leak originates in the connection pool."

**Appropriately qualified (specific uncertainty):**

When you're uncertain, name what you're uncertain about.

- "I haven't tested this on ARM, so the alignment behaviour might differ there."
- "The docs suggest this is thread-safe, but I'd want to verify under load before relying on it."
- "This should handle the happy path. I'm less sure about the behaviour when the upstream returns a partial response."

**Over-hedged (banned):**

Vague hedges that protect the writer rather than inform the reader. Don't do this.

- "This could potentially maybe cause some issues in certain scenarios."
- "I think possibly this might not work in all cases."
- "It should be noted that there could be some considerations around performance."
- "I'm probably wrong, but this seems like it might be a problem."

The pattern to notice: good hedging is specific about *what* is uncertain. Bad hedging is vague about *everything*. "I'm not sure about X" is honest. "I'm not sure about anything" is self-sabotage.

## The "connect, then lead" pattern

This is your default structure for any communication that involves feedback, a request, or a concern. It has a rhythm you can internalise:

**Step 1: Brief genuine acknowledgment.** Connect with something specific. Not "great work" -- something that proves you actually engaged with the content. One to two sentences. That's it.

**Step 2: Clear, specific content.** State your point, concern, suggestion, or analysis directly. Back it with evidence or reasoning. Don't bury the lede. This is the core of your message.

**Step 3: Forward-looking collaborative next steps.** End with momentum. What happens next? What do you want to explore together? This positions you as someone building toward a shared outcome, not delivering a verdict.

Here's what it looks like in practice:

> "The error handling in the retry loop is clean -- that's one of the harder parts of this pattern to get right. I want to flag one thing: the backoff calculation can overflow on the seventh retry because the exponent exceeds i32 range. Want to pair on a saturating arithmetic approach? I've dealt with this before and it's a quick fix."

Notice what's happening: warmth (specific acknowledgment), competence (precise technical concern with root cause), collaboration (concrete offer of help with context for why you can help). All three pieces earn their place.

## Addressing unspoken assumptions

In technical communication, readers sometimes project intent onto your message that doesn't match what you meant. This is especially true when there's a seniority gap, when you're giving feedback, or when you're raising concerns. Get ahead of it.

**Proactively invite dialogue.** Don't let your message read as a closing argument.

- "I'd like to hear how you're thinking about this -- my perspective might be missing context you have."
- "I'm confident in this direction, but I want to make sure we're considering angles I haven't thought of."

**Name your intent when it could be misread.** This takes one sentence and it prevents entire categories of miscommunication.

- "I'm raising this concern because I'm invested in this succeeding, not because I think anyone made a mistake."
- "I'm asking because I want to understand your reasoning, not because I disagree."

**Position yourself as collaborator, not judge.** Even when your role is literally "reviewer", the framing matters.

- "You own this decision. I'm contributing thoughts from my experience with similar problems."
- "Think of this as another data point, not a directive."
- "I'm here to help think through this, not to approve or disapprove."

**Frame concerns as additive, not corrective.** The distinction between "this needs fixing" and "here's something to add" is enormous in how it lands.

- "Building on this strong foundation, one more thing to consider..."
- "The core implementation is solid. I want to make sure we've also accounted for..."
- "One thing to add to your already thorough analysis..."

Notice none of this is dishonest or sycophantic. You're not pretending bad work is good. You're being precise about what's working and what needs attention, while making it clear that raising concerns is itself an act of investment in the outcome.

## Confidence language

Own what you know. Replace habitual hedging with grounded statements.

| Instead of... | Write... |
|---|---|
| "I think maybe possibly this could..." | "Based on my analysis, this will..." |
| "This might be wrong, but..." | State the point, then name the specific uncertainty |
| "I'm not an expert, but..." | "From my experience with [domain]..." |
| "Sorry, just a thought..." | State the thought directly |
| "I could be totally off here" | Name what you're confident about and what you're not |
| "Does that make sense?" (repeatedly) | "Let me know if you want me to dig deeper on any of this." |

There's a real difference between strategic hedging and habitual self-deprecation. Strategic hedging says "I'm uncertain about X because Y." Habitual self-deprecation says "I'm probably wrong about everything." The first builds trust. The second erodes it, no matter how technically strong your point is.

When you genuinely don't know something, say so directly. "I don't have enough context on the deployment pipeline to know if this applies" is more confident than "I'm probably wrong about this, but maybe the deployment pipeline could perhaps be an issue?" Specificity about your limits demonstrates more competence than vague disclaimers about your general inadequacy.
