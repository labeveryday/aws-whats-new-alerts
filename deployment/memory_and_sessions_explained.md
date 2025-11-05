# Memory and Sessions in AgentCore - Complete Guide

## 1. How Memories Are Added BY the Agent

### The Memory Flow:
```
User Request → Agent Processing → Tool Calls → Agent Response → Memory Hook Saves
```

### Step-by-Step Example:

```python
# 1. User calls your newsletter agent
POST /invocations {"prompt": "Generate today's newsletter"}

# 2. Agent processes with tools
agent.call("http_request", url="https://aws.amazon.com/new/")
agent.call("current_time")
# Agent creates newsletter content

# 3. Memory hook automatically triggers AFTER agent responds
def on_message_added(self, event):
    msg = event.agent.messages[-1]  # Last message (agent's response)
    
    # This is where memory gets saved:
    self.memory_client.create_event(
        memory_id=MEMORY_ID,
        actor_id="newsletter-agent", 
        session_id="newsletter-2025-01-27",
        messages=[("Newsletter generated: 5 AI articles processed...", "assistant")]
    )
```

### What Gets Saved:
- **Conversations**: Agent's responses, tool results
- **Processing Results**: "Processed 5 articles, sent newsletter"
- **Context**: Date, session info, processing details

## 2. Understanding Sessions

### Session Concept:
A **session** is like a "conversation thread" or "processing context"

### In Your Newsletter Agent Context:

#### Option A: Daily Sessions (Recommended for Newsletter)
```python
# Each day = new session
session_id = f"newsletter-{date.today().isoformat()}"
# Examples:
# "newsletter-2025-01-27"
# "newsletter-2025-01-28" 
# "newsletter-2025-01-29"
```

#### Option B: Single Persistent Session
```python
# Same session always
session_id = "newsletter-agent-main"
```

#### Option C: User-Based Sessions
```python
# Different session per user
session_id = f"newsletter-user-{user_id}"
```

## 3. Memory Organization Structure

```
Memory Store (newsletter_agent_memory)
├── Actor: "newsletter-agent"
│   ├── Session: "newsletter-2025-01-27"
│   │   ├── Turn 1: "Generated newsletter with 3 AI articles"
│   │   └── Turn 2: "Sent newsletter to SNS topic"
│   ├── Session: "newsletter-2025-01-28" 
│   │   ├── Turn 1: "No new articles found today"
│   │   └── Turn 2: "Sent 'nothing new' newsletter"
│   └── Session: "newsletter-2025-01-29"
│       └── Turn 1: "Found 7 new AI articles..."
```

## 4. Memory Retrieval - What the Agent Sees

### When Agent Starts (on_agent_initialized):
```python
# Agent asks: "What happened recently?"
turns = memory_client.get_last_k_turns(
    memory_id=MEMORY_ID,
    actor_id="newsletter-agent",
    session_id="newsletter-2025-01-27",  # Current session
    k=3  # Last 3 interactions
)

# Agent gets back:
# [
#   ["Generated newsletter with 3 AI articles", "assistant"],
#   ["Sent newsletter to SNS topic", "assistant"], 
#   ["Processing completed successfully", "assistant"]
# ]
```

### Session Isolation:
- **Same session**: Agent sees all previous turns in that session
- **Different session**: Agent sees NOTHING from other sessions (unless you query across sessions)

## 5. Your Newsletter Agent Session Strategy

### Current Code Analysis:
```python
# In your agent_fixed.py:
state={"session_id": f"newsletter-{date.today().isoformat()}"}

# This means:
# - January 27: session = "newsletter-2025-01-27"
# - January 28: session = "newsletter-2025-01-28"  
# - Each day gets its own session
```

### What This Means:

#### Scenario: Newsletter Runs Daily

**Day 1 (Jan 27)**:
```
Session: "newsletter-2025-01-27"
- Agent starts with NO memory (new session)
- Processes articles, finds 5 new AI articles
- Saves: "Processed 5 AI articles: Claude update, SageMaker..."
- Sends newsletter
```

**Day 2 (Jan 28)**:
```
Session: "newsletter-2025-01-28" 
- Agent starts with NO memory from Day 1 (different session!)
- Processes articles independently
- Might process same articles again (no cross-day memory)
```

### Problem with Daily Sessions:
❌ **Agent can't remember what it processed yesterday**
❌ **Might send duplicate articles**
❌ **No learning across days**

## 6. Better Session Strategies for Newsletter

### Strategy 1: Weekly Sessions (Recommended)
```python
# Group by week
week_num = date.today().isocalendar()[1]
session_id = f"newsletter-2025-week-{week_num}"

# Results:
# Week 4: "newsletter-2025-week-4" 
# Week 5: "newsletter-2025-week-5"
# All days in same week share memory
```

### Strategy 2: Monthly Sessions
```python
# Group by month  
session_id = f"newsletter-{date.today().strftime('%Y-%m')}"

# Results:
# "newsletter-2025-01" (all of January)
# "newsletter-2025-02" (all of February)
```

### Strategy 3: Single Persistent Session
```python
# One session for everything
session_id = "newsletter-main"

# Agent remembers EVERYTHING ever processed
# Might get overwhelming with too much history
```

## 7. Cross-Session Memory Access

### If You Want Memory Across Sessions:
```python
def on_agent_initialized(self, event):
    # Get memory from multiple recent sessions
    recent_sessions = [
        f"newsletter-{(date.today() - timedelta(days=i)).isoformat()}"
        for i in range(7)  # Last 7 days
    ]
    
    all_recent_memory = []
    for session in recent_sessions:
        turns = self.memory_client.get_last_k_turns(
            memory_id=MEMORY_ID,
            actor_id="newsletter-agent",
            session_id=session,
            k=2
        )
        all_recent_memory.extend(turns)
    
    # Now agent sees memory from multiple days
```

## 8. Recommended Setup for Your Newsletter

### Option A: Weekly Sessions (Best Balance)
```python
# In agent_fixed.py, replace:
week_num = date.today().isocalendar()[1] 
session_id = f"newsletter-2025-week-{week_num}"

# Benefits:
# ✅ Remembers within same week
# ✅ Prevents duplicate processing for a few days  
# ✅ Not too much memory accumulation
# ✅ Natural reset each week
```

### Option B: Rolling 7-Day Memory
```python
# Always remember last 7 days regardless of session
def get_recent_processing_memory(self):
    memories = []
    for i in range(7):  # Last 7 days
        past_date = date.today() - timedelta(days=i)
        session = f"newsletter-{past_date.isoformat()}"
        turns = self.memory_client.get_last_k_turns(
            memory_id=MEMORY_ID,
            actor_id="newsletter-agent", 
            session_id=session,
            k=1
        )
        memories.extend(turns)
    return memories
```

## 9. Memory Privacy and Access

### Important: Memory is NOT per-user automatically
- **Same memory store** for all users of your agent
- **Session isolation** prevents users seeing each other's sessions
- **Actor isolation** prevents different agents from seeing each other

### For Newsletter Agent:
- **Single actor** ("newsletter-agent") 
- **Sessions by time period** (daily/weekly)
- **All users see same newsletter** (which is what you want)

### If You Had User-Specific Features:
```python
# Different approach for user-specific agents
actor_id = f"user-{user_id}"  # Each user gets own memory
session_id = f"conversation-{session_uuid}"
```

## 10. Summary Recommendations

### For Your Newsletter Agent:

1. **Use Weekly Sessions**:
   ```python
   week_num = date.today().isocalendar()[1]
   session_id = f"newsletter-2025-week-{week_num}"
   ```

2. **Keep Single Actor**:
   ```python
   actor_id = "newsletter-agent"  # Same for all processing
   ```

3. **Memory Hook Saves**:
   - Processing results
   - Article summaries  
   - Newsletter status

4. **Memory Hook Loads**:
   - Recent processing within same week
   - Prevents duplicate article processing
   - Maintains context

This gives you the best balance of memory continuity without overwhelming the agent with too much history.