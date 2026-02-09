-- Migration 001: pgvector setup for conversation embeddings
-- Run this in Supabase SQL Editor (Dashboard > SQL Editor)
-- Requires pgvector extension to be enabled in Supabase Dashboard > Database > Extensions

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create conversation embeddings table
CREATE TABLE IF NOT EXISTS conversation_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    conversation_id UUID NOT NULL,
    message_id UUID NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    embedding vector(1536),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for user + conversation lookups
CREATE INDEX IF NOT EXISTS idx_conv_emb_user_conv
    ON conversation_embeddings (user_id, conversation_id);

-- Index for vector similarity search using IVFFlat
-- Note: IVFFlat requires at least some data to build properly
-- For small datasets, HNSW is recommended instead
CREATE INDEX IF NOT EXISTS idx_conv_emb_embedding
    ON conversation_embeddings
    USING hnsw (embedding vector_cosine_ops);

-- Index for created_at for time-based queries
CREATE INDEX IF NOT EXISTS idx_conv_emb_created
    ON conversation_embeddings (created_at DESC);

-- RPC function for vector similarity search
-- Called from the application: supabase.rpc("match_conversations", params)
CREATE OR REPLACE FUNCTION match_conversations(
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.5,
    match_count INT DEFAULT 10,
    filter_user_id UUID DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    user_id UUID,
    conversation_id UUID,
    message_id UUID,
    role VARCHAR(20),
    content TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        ce.id,
        ce.user_id,
        ce.conversation_id,
        ce.message_id,
        ce.role,
        ce.content,
        ce.created_at,
        1 - (ce.embedding <=> query_embedding) AS similarity
    FROM conversation_embeddings ce
    WHERE
        (filter_user_id IS NULL OR ce.user_id = filter_user_id)
        AND 1 - (ce.embedding <=> query_embedding) > match_threshold
    ORDER BY ce.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Enable Row Level Security
ALTER TABLE conversation_embeddings ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only access their own embeddings
CREATE POLICY "Users can view own conversation embeddings"
    ON conversation_embeddings
    FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own conversation embeddings"
    ON conversation_embeddings
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own conversation embeddings"
    ON conversation_embeddings
    FOR DELETE
    USING (auth.uid() = user_id);

-- Service role can access all (bypasses RLS when using service_role key)
