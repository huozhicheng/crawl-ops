# 构建阶段
FROM node:18-alpine AS builder

# 设置时区
RUN apk add --no-cache tzdata
ENV TZ=Asia/Shanghai

# 安装 pnpm
RUN corepack enable && corepack prepare pnpm@8.14.0 --activate

WORKDIR /app

# 复制依赖文件
COPY package.json pnpm-lock.yaml ./

# 严格按锁文件安装，确保镜像使用已验证的依赖版本
RUN pnpm install --frozen-lockfile

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
