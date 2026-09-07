# Owner question format

One message per recipient per run. Recipients come from `ListAgents` rows marked idle or waiting
at send time. Idle status changes within minutes, so take the listing right before sending, and
for a busy owner subscribe with `SendMessage` `notify_when_idle: true` (no body) instead of polling.

## Message

```
Disk-space question from the "<your session name>" session: are <paths, each with size and state>
still needed as evidence, or is everything you need from them already written to disk under
<expected artifact dir or pushed branch>?

This machine has <free space> free (<when measured>). I did NOT touch <paths> because <the census
basis: dirty tree, unpushed commits, experiment tag, live process>. Please reply with exactly one
of these per path (group paths that share an answer):
- KEEP <reason, one line; add "until <path-exists or time>" if it is time-bounded>
- SAFE <what on-disk artifact or pushed branch already holds the work>
- UNKNOWN <who could say>

You may clean up your own scratch under these paths if you are sure; tell me what you removed.
Reply with SendMessage to "<your session name>". Ignore if you are mid-task; I will not ask again
this session.
```

The last paragraph says what to do rather than forbidding cleanup, because in measurement both
owners cleaned up their own scratch anyway when the message said "do not delete anything
yourself". Asking them to report what they removed keeps the census numbers honest.

## Reading a reply, then recording it

A reply that is not recorded does not exist to the executor. For each verdict line:

```
disk_reclaim_record.py --path <exact path> --bytes <census bytes> --cmd "<census reclaim_cmd>" \
  --decided-by "owner:<session name>" --verdict SAFE|KEEP|UNKNOWN [--until "<condition>"] [--note "<what they removed>"]
```

`disk_reclaim.py` allows a path only on an owner SAFE, a human email, or (for ownerless caches only) `auto:cache`. A KEEP blocks it; an UNKNOWN or no reply leaves it for the human.

- Take each verdict line's token: KEEP, SAFE, or UNKNOWN. Ignore any preamble ("Per-path
  verdicts:", "Inventory:"); grade lines, not the first word of the message.
- SAFE without a named artifact or branch is UNKNOWN.
- A KEEP with "until" is a deferred row: store the condition in the ledger so the next census can
  re-ask when it is met.
- A reply that volunteers paths you did not name is a census candidate, not a decision.
- No reply within the deadline (10 minutes) means the row stays unknown and goes to the human.

## Why this shape

Measured on one machine with twelve live sessions: three structured recipients, two replied within
minutes, cited committed artifacts, and gave a verdict on exactly the bytes named; the third had
been idle for five days and never replied. A free-text baseline ("anything you manage that is safe
to delete?") produced a careful inventory of kilobyte-scale files and closed with "nothing I manage
is a meaningful win". Format, not effort, made the difference: the recipient needs the census's
numbers to react to.
