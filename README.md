# XHS + YouTube Skills

This repository packages two reusable AI skill modules with a similar content-processing workflow:

- `xhs-to-notion/`: fetches Xiaohongshu content, summarizes it with built-in AI, and archives the result into Notion
- `youtube-to-novel/`: turns YouTube videos or podcast-style content into a novel-writing workflow with multimodal analysis

## Repository Structure

- `xhs-to-notion/SKILL.md`: skill description and execution flow for Xiaohongshu ingestion and Notion export
- `xhs-to-notion/README.md`: installation notes and usage examples for the Xiaohongshu workflow
- `youtube-to-novel/SKILL.md`: skill description and generation flow for turning long-form media into fiction
- `youtube-to-novel/README.md`: installation notes and usage examples for the novel workflow
- `youtube-to-novel/prompts/`: prompt templates for frame analysis and chapter writing
- `youtube-to-novel/references/`: command references and subtitle format notes

## Shared Workflow Pattern

- Accept a user-provided content link or local media input
- Extract source material into structured intermediate artifacts
- Use built-in AI to summarize, transform, or expand the source content
- Return a polished output artifact for downstream use such as Notion archiving or long-form writing

## XHS Workflow Highlights

- Fetches note content, metadata, and images into a local artifact directory
- Uses the agent's built-in AI to generate a structured summary without requiring a separate model API key
- Exports summarized content into Notion when credentials are configured
- Supports a degraded mode where users can stop at fetch plus summary

## YouTube Workflow Highlights

- Accepts YouTube links, local video or audio files, and podcast RSS sources
- Combines subtitle extraction, keyframe analysis, and multimodal understanding
- Builds a novel outline, chapter plan, and long-form text with continuity controls
- Includes reusable prompt and reference files for the full pipeline

## Notes

- Secrets are not stored in this repository
- `xhs-to-notion/` depends on a local Xiaohongshu scraping project and user-provided cookies
- `youtube-to-novel/` requires system tools such as `ffmpeg` and Python packages such as `yt-dlp`
