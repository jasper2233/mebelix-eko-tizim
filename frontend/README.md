# MebeliX MES — Frontend

The frontend is built with [Vite](https://vitejs.dev/), [React](https://reactjs.org/), [TypeScript](https://www.typescriptlang.org/), [TanStack Query](https://tanstack.com/query), [TanStack Router](https://tanstack.com/router) and [Tailwind CSS](https://tailwindcss.com/).

## Frontend development

Before you begin, ensure that you have either the Node Version Manager (nvm) or Fast Node Manager (fnm) installed on your system.

* To install fnm follow the [official fnm guide](https://github.com/Schniz/fnm#installation). If you prefer nvm, you can install it using the [official nvm guide](https://github.com/nvm-sh/nvm#installing-and-updating).

* After installing either nvm or fnm, proceed to the `frontend` directory:

```bash
cd frontend
```
* If the Node.js version specified in the `.nvmrc` file isn't installed on your system, you can install it using the appropriate command:

```bash
# If using fnm
fnm install

# If using nvm
nvm install
```

* Once the installation is complete, switch to the installed version:

```bash
# If using fnm
fnm use

# If using nvm
nvm use
```

* Within the `frontend` directory, install the necessary NPM packages:

```bash
npm install
```
*(Or use `make frontend-install` from the project root)*

* And start the live server with the following `npm` script:

```bash
npm run dev
```
*(Or use `make run-frontend` from the project root)*

* Then open your browser at http://localhost:5173/.

Notice that this live server is not running inside Docker, it's for local development, and that is the recommended workflow. Once you are happy with your frontend, you can build the frontend Docker image and start it, to test it in a production-like environment. But building the image at every change will not be as productive as running the local development server with live reload.

Check the file `package.json` to see other available options.

## Generate Client

### Automatically

From the top level project directory, run:

```bash
make frontend-gen
```

*(This runs the `scripts/generate-client.sh` script which handles everything)*

### Manually

The manual flow mirrors what `scripts/generate-client.sh` does:

* Export the OpenAPI schema directly from the backend app (no server needed) into `openapi.json` at the root of the `frontend` directory:

```bash
cd backend
uv run python -c "import app.main; import json; print(json.dumps(app.main.app.openapi()))" > ../frontend/openapi.json
```

*(Alternatively, with the backend running locally you can download it from `http://localhost:8000/openapi.json` — note it is served at the app root, not under `/api/v1`, and only in non-production environments.)*

* To generate the frontend client, run (inside `frontend/`):

```bash
npm run generate-client
npx biome format --write ./src/client
```

* Commit the changes.

Notice that everytime the backend changes (changing the OpenAPI schema), you should follow these steps again to update the frontend client.

## Using a Remote API

If you want to use a remote API, you can set the environment variable `VITE_API_URL` to the URL of the remote API. For example, you can set it in the `frontend/.env` file:

```env
VITE_API_URL=https://api.my-domain.example.com
```

Then, when you run the frontend, it will use that URL as the base URL for the API.

## Code Structure

The frontend code is structured as follows:

* `frontend/src` - The main frontend code.
* `frontend/src/client` - The generated OpenAPI client.
* `frontend/src/components` -  The different components of the frontend.
* `frontend/src/hooks` - Custom hooks.
* `frontend/src/lib` - Shared helpers: MES domain constants and formatting (`mes.ts`), zod schemas and input formatters (`validation.ts`), utilities (`utils.ts`).
* `frontend/src/queries` - TanStack Query option factories (`mes.ts`, `users.ts`).
* `frontend/src/routes` - The different routes of the frontend which include the pages.
* `frontend/public/assets` - Static assets (served as `/assets/*`).
