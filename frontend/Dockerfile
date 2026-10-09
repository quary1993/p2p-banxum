FROM public.ecr.aws/docker/library/node:22-alpine

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend .

EXPOSE 5173
