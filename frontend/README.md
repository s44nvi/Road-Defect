# Frontend

Next.js and React dashboard for municipal officers.

## Tech Stack

- **Framework:** Next.js 14+ with TypeScript
- **UI Library:** React 18+
- **Mapping:** Mapbox GL JS or Leaflet
- **State Management:** React Context API / TanStack Query
- **Styling:** Tailwind CSS
- **Build:** Node.js 18+

## Project Structure

Routes and components are organized around the municipal officer workflow:

```text
frontend/
  app/
    dashboard/        Map and priority queue view
    defect/[id]/      Persistent defect detail and evidence panel
    verify/           Officer confirmation workflow
    repair/[id]/      Before/after repair comparison
  components/         Reusable UI components
    map/              Map integration and controls
    queue/            Priority queue display
    evidence-panel/   Evidence visualization
  lib/
    api.ts            Single backend client boundary
```

## Key Principles

- Components consume backend read models and do not duplicate ML or priority logic
- All API calls route through `lib/api.ts` for consistent error handling and authentication
- Real-time map updates via WebSocket or polling

## Setup

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
npm start
```

## Environment Variables

Create `.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_MAPBOX_TOKEN=your_token_here
```