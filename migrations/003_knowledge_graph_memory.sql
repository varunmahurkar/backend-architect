-- Migration 003: Knowledge Graph + User Memory tables
-- Run this in your Supabase SQL editor before using knowledge_graph_* and memory_recall tools.

-- Knowledge graph nodes
CREATE TABLE IF NOT EXISTS kg_nodes (
    id TEXT NOT NULL,
    user_id TEXT NOT NULL DEFAULT 'global',
    label TEXT,
    type TEXT DEFAULT 'concept',
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (id, user_id)
);

-- Knowledge graph edges
CREATE TABLE IF NOT EXISTS kg_edges (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'global',
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    relation TEXT DEFAULT 'related_to',
    weight FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kg_edges_user ON kg_edges (user_id);
CREATE INDEX IF NOT EXISTS idx_kg_nodes_user ON kg_nodes (user_id);

-- User memories / preferences
CREATE TABLE IF NOT EXISTS user_memories (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,   -- 'preference' | 'topic' | 'interaction'
    key TEXT NOT NULL,
    value JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, category, key)
);

CREATE INDEX IF NOT EXISTS idx_user_memories_user ON user_memories (user_id);
