FROM node:22-slim

WORKDIR /app

COPY package.json ./
RUN npm install

COPY index.html ./
COPY tsconfig*.json ./
COPY vite.config.ts ./
COPY src ./src

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
