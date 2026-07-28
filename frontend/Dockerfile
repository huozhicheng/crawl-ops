# 构建阶段
FROM node:18-alpine AS builder

# 设置时区
RUN apk add --no-cache tzdata
ENV TZ=Asia/Shanghai

# 安装 pnpm
RUN corepack enable && corepack prepare pnpm@8.14.0 --activate

WORKDIR /app

# 复制依赖文件
COPY package.json ./

# 安装依赖（不使用frozen-lockfile，因为没有lock文件）
RUN pnpm install

# 复制源码并构建
COPY . .
RUN pnpm build

# 生产阶段
FROM nginx:alpine

# 设置时区
RUN apk add --no-cache tzdata
ENV TZ=Asia/Shanghai

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
