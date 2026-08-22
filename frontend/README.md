# Frontend

Next.js and React dashboard for municipal officers.

Routes and components are organized around the municipal officer workflow:

```text
frontend/
	app/dashboard/       Map and priority queue
	app/defect/[id]/      Persistent defect detail
	app/verify/           Officer confirmation workflow
	app/repair/[id]/      Before/after repair comparison
	components/           Map, queue, and evidence panel components
	lib/api.ts            Single backend client boundary
```

Components consume backend read models and do not duplicate ML or priority logic.