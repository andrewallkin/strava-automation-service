A good running-plan system is less about “generate a plan” and more about building a reliable decision pipeline:

1. Understand the athlete.
2. Understand the constraints.
3. Understand the event demands.
4. Understand current fitness/load.
5. Detect risks/conflicts.
6. Build macro structure.
7. Build weekly sessions.
8. Validate realism.
9. Output structured data.

Your Strava MCP server becomes extremely valuable because it lets the system ground recommendations in actual training history instead of self-reported estimates.

---

# 1. Information You Need From the User

Think of this in layers.

---

# A. Athlete Profile

This establishes the baseline identity of the athlete.

## Required

* Age
* Sex (optional but useful physiologically)
* Height / weight (optional)
* Running experience level

  * beginner
  * intermediate
  * advanced
* Years running consistently
* Typical weekly mileage / volume
* Longest recent run
* Current training consistency

  * e.g. “running 5x/week consistently for 6 months”

## Why this matters

This determines:

* training durability
* progression rate
* recovery assumptions
* injury risk
* realistic weekly structure

---

# B. Goal Events / Races

This is the most important planning input.

## Required per race

* Race name
* Race date
* Race type

  * 5k
  * 10k
  * half marathon
  * marathon
  * ultra
  * trail
  * triathlon
* Priority

  * A race
  * B race
  * C race
* Goal

  * finish
  * PB
  * qualification
  * podium
* Goal time (if applicable)
* Terrain

  * road
  * trail
  * mountainous
* Elevation profile if relevant
* Expected weather/climate if destination race

## Why this matters

The plan architecture changes massively depending on:

* duration
* specificity
* terrain
* race priority
* available preparation time

---

# C. Availability & Scheduling Constraints

This is where most plans fail in real life.

## Required

* Number of running days available per week
* Preferred rest day(s)
* Maximum weekday workout duration
* Maximum weekend workout duration
* Non-negotiable unavailable days
* Preferred long run day
* Preferred workout day(s)

## Optional but powerful

* Travel schedule
* Work stress periods
* Shift work
* Parenting constraints
* Gym access
* Safe running times
* Climate restrictions

## Why this matters

The best physiological plan is useless if it doesn’t fit the athlete’s life.

---

# D. Current Fitness & Performance

This determines training paces and progression.

## Required

At least one of:

* Recent race results
* Time trial results
* Estimated threshold pace
* Estimated 5k pace
* Estimated marathon pace

## Very Valuable

From Strava MCP:

* CTL-like metrics
* Weekly mileage trend
* Pace distribution
* Long run history
* Elevation exposure
* Heart rate data
* Training load trend
* Acute/chronic load ratio
* Frequency consistency
* Recent workouts
* Fatigue indicators

## Why this matters

Without this:

* intensity prescription is weak
* progression is guesswork
* overload risk increases

---

# E. Injury & Health History

Critical for safe planning.

## Required

* Current injuries
* Recent injuries
* Chronic issues
* Areas prone to injury
* Any medical limitations

## Important

* Sleep quality
* Recovery quality
* Stress levels
* Nutrition issues

## Why this matters

This heavily affects:

* volume ramp rate
* intensity frequency
* workout selection
* recovery week frequency

---

# F. Training Preferences

This increases adherence.

## Examples

* Likes long runs
* Hates track workouts
* Prefers trails
* Likes structured intervals
* Wants polarized training
* Wants heart-rate-based training
* Wants pace-based training
* Wants flexible plans

## Why this matters

Adherence > optimality.

---

# G. Cross Training & Strength

## Gather

* Cycling/swimming/gym work
* Strength training frequency
* Other sports
* Desired integration

## Why this matters

Total stress matters more than just running volume.

---

# H. Device / Metrics Ecosystem

Optional but useful.

## Gather

* Garmin/Coros/Apple Watch
* Heart rate available?
* Power meter?
* Strava connected?
* GPS accuracy issues?
* Indoor treadmill use?

## Why this matters

Determines:

* metric precision
* session prescription format
* what can be monitored automatically

---

# I. Planning Philosophy Preferences

Optional but useful.

## Examples

* Conservative progression
* Aggressive performance focus
* Low injury risk
* High mileage preference
* Minimal intensity
* Science-heavy structure
* Flexible adaptive plan

---

# 2. Information You Should Derive Automatically From Strava

This is where your MCP server becomes a competitive advantage.

Do not ask users for things you can infer reliably.

---

# Automatically Derived Metrics

## Volume Metrics

* Weekly mileage
* Long run average
* Frequency
* Consistency streaks
* Volume trend

## Intensity Metrics

* Pace zones
* HR zones
* Threshold estimates
* Fast finish capability
* Workout density

## Durability Metrics

* Long run recovery
* Back-to-back tolerance
* Fatigue after hard sessions

## Terrain Metrics

* Elevation exposure
* Trail vs road ratio

## Training Patterns

* Preferred run days
* Missed training patterns
* Weekend emphasis
* Overtraining tendencies

## Performance Trends

* Pace improvement
* HR drift
* Efficiency changes
* Race progression

---

# 3. Recommended Multi-Agent System

Do NOT make one giant planner agent.

You want specialized agents with narrow responsibilities and structured outputs between them.

---

# High-Level Architecture

Think of this as:

User + Strava
↓
Profile Understanding
↓
Constraint Resolution
↓
Fitness Analysis
↓
Race Strategy
↓
Macro Plan
↓
Weekly Construction
↓
Workout Construction
↓
Validation
↓
Structured Output

---

# Recommended Agents

---

# 1. Intake / Conversation Agent

## Responsibility

Talk to the user naturally.

Gather missing information progressively.

Not one-shot.

## Why separate?

You want:

* conversational memory
* clarification handling
* ambiguity resolution

This agent should NOT build plans.

## Outputs

Structured athlete profile:

* athlete info
* constraints
* goals
* preferences

---

# 2. Strava Analysis Agent

## Responsibility

Use MCP tools to analyze:

* current fitness
* historical load
* consistency
* recent workouts
* trends

## Why separate?

Tool-heavy reasoning should be isolated.

This agent converts raw activity data into structured insights.

## Outputs

Things like:

* current estimated fitness
* sustainable volume
* injury risk indicators
* recommended starting load
* training zones

---

# 3. Race Demands Agent

## Responsibility

Understand what the goal race physiologically requires.

## Example

A marathon requires:

* aerobic durability
* glycogen management
* marathon pace efficiency

A mountain ultra requires:

* climbing durability
* hiking efficiency
* eccentric load tolerance

## Outputs

Race requirement profile:

* energy systems
* long run needs
* peak volume range
* specificity needs

---

# 4. Constraint & Feasibility Agent

## Responsibility

Reconcile:

* available time
* race goals
* current fitness
* timeline

## Why important?

This is the realism agent.

It prevents:

* impossible goals
* unsafe ramp rates
* overcommitment

## Example decisions

* “Sub-3 marathon not realistic in 10 weeks.”
* “Need reduced volume due to injury history.”

---

# 5. Macrocycle Planning Agent

## Responsibility

Create the high-level training phases.

## Example

12-week marathon:

* Base
* Build
* Specific
* Taper

## Determines

* weekly volume progression
* cutback weeks
* peak timing
* workout emphasis shifts

## Output

Structured weekly blueprint.

---

# 6. Mesocycle Agent

## Responsibility

Design 2–6 week blocks.

## Why separate?

Good plans are block-based.

This agent defines:

* focus of each block
* progression strategy
* workout density

---

# 7. Weekly Planning Agent

## Responsibility

Generate actual week layouts.

## Example

Monday: Rest
Tuesday: Threshold
Wednesday: Easy
Thursday: VO2
Friday: Rest
Saturday: Long Run
Sunday: Recovery

## Must consider

* user schedule
* recovery spacing
* long run timing
* workout sequencing

---

# 8. Workout Design Agent

## Responsibility

Generate the exact sessions.

## Example

Instead of:
“Tempo run”

Generate:

* warmup
* intervals
* recovery
* cooldown
* pace/HR targets
* intent

## Why separate?

Workout prescription logic is highly specialized.

---

# 9. Recovery & Risk Agent

## Responsibility

Audit the plan for:

* overload
* injury risk
* excessive intensity
* insufficient recovery

## Why important?

LLMs tend to overprescribe.

This agent acts as a safety layer.

---

# 10. Adaptation / Feedback Agent

## Responsibility

Update the plan dynamically over time.

Using:

* missed runs
* fatigue
* Strava updates
* race results

## This becomes extremely valuable

This is where AI systems become much better than static plans.

---

# 11. Structured Output Agent

## Responsibility

Convert everything into strict structured JSON.

## Why separate?

You want:

* formatting reliability
* schema compliance
* frontend compatibility

This agent should ONLY format and validate.

---

# 4. Recommended Structured Output Shape

Your final output should probably include:

```json
{
  "plan_metadata": {},
  "athlete_profile": {},
  "race_targets": [],
  "training_zones": {},
  "weeks": [
    {
      "week_number": 1,
      "focus": "base",
      "volume_target_km": 55,
      "days": [
        {
          "date": "",
          "session_type": "easy",
          "description": "",
          "duration_minutes": 50,
          "distance_km": 10,
          "targets": {
            "pace": "",
            "heart_rate": ""
          }
        }
      ]
    }
  ]
}
```

---

# 5. Important System Design Principles

---

# A. Do Not Let One Agent Do Everything

Single-agent systems:

* become inconsistent
* hallucinate structure
* ignore constraints
* struggle with long horizons

---

# B. Use Structured Outputs Between Agents

Each agent should produce:

* validated JSON
* typed outputs
* minimal ambiguity

---

# C. Separate Reasoning from Formatting

Very important.

Planning agents:

* think

Formatter agent:

* validates schema

---

# D. Use Deterministic Validation Layers

Not just LLMs.

You should also validate:

* no impossible mileage jumps
* no double hard days
* taper logic
* schedule conflicts

with actual code rules.

---

# E. Build for Iteration

The system should support:

* regenerate week
* modify workout
* adapt for illness
* add races
* reduce load

without rebuilding the entire plan.

---

# 6. Most Important Hidden Problem

The hardest part is NOT generating workouts.

It is balancing:

* realism
* progression
* recovery
* user lifestyle
* race specificity
* long-term consistency

That is why the constraint/recovery/feasibility agents are extremely important.