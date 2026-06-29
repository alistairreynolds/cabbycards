# Dev-mode image: runs the Vite dev server (good enough to boot and look at).
FROM node:22-alpine

RUN corepack enable

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

EXPOSE 5173

# --host binds 0.0.0.0 so the dev server is reachable from the host.
CMD ["pnpm", "dev", "--host", "0.0.0.0"]
