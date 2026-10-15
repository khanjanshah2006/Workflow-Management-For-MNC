# WorkSphere Frontend

WorkSphere is an Enterprise Workflow Management System frontend built with React and Vite.

## Prerequisites

- Node.js and npm

## Installation

From the repository root, run:

    cd frontend
    npm install

## Run locally

    npm run dev

Open the local URL shown in the terminal.

## Production build

    npm run build

## Routes

- `/login` — Login placeholder
- `/dashboard` — Dashboard placeholder
- `/projects` — Projects placeholder
- `/tasks` — Tasks placeholder
- `/profile` — Profile placeholder

## Environment

The `.env.example` file documents the `VITE_API_BASE_URL` setting.

For local development, create `.env.local` from `.env.example` and configure the backend URL when available. Never commit real secrets or `.env.local`.

## Current scope

This frontend foundation provides shared navigation, layout, routing, and responsive styling. Feature-specific login and dashboard functionality is handled separately.