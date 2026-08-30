# Hot Take

## The uncomfortable truth about "agentic" systems

Most multi-agent systems in hackathon projects are over-engineered.
A single well-prompted LLM call often achieves 70-80% of the benefit
with 10% of the complexity.

WorthApply was built to test this honestly.

The baseline is a single prompt. Every additional agent was added
only when the baseline's measured failures justified it. Some agents
were removed when they didn't meaningfully improve results.

The real question isn't "how many agents can we use?" — it's
"does this agent earn its keep?"

If the baseline achieves 85% accuracy and the multi-agent system
achieves 88% at 5x the cost and 4x the latency, is it worth it?

Sometimes yes (if that 3% catches critical risk signals).
Sometimes no (if the improvement is just cosmetic).

We tracked this honestly. The changelog shows what worked,
what didn't, and what we removed. That's the real contribution.
