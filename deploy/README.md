# 重明 (ChongMing) 部署指南

## 📁 目录结构

```
deploy/
├── openapi.yaml           # OpenAPI 3.0 API 文档
├── docker-compose.yml     # Docker Compose 配置
├── .env.example           # 环境变量模板
├── init.sql               # 数据库初始化脚本
├── prometheus.yml         # Prometheus 监控配置
├── nginx/
│   └── nginx.conf         # Nginx 反向代理配置
└── kubernetes/
    └── chongming.yaml     # Kubernetes 部署清单
```

---

## 🐳 Docker Compose 部署

### 快速启动

```bash
# 1. 复制环境变量
cp .env.example .env

# 2. 编辑 .env，填写 QWEN_API_KEY
vim .env

# 3. 启动所有服务
docker-compose up -d

# 4. 查看日志
docker-compose logs -f api-gateway
```

### 服务端口

| 服务 | 端口 | 用途 |
|------|------|------|
| Frontend | 3000 | 前端 UI |
| API Gateway | 8000 | 后端 API |
| Flower | 5555 | Celery 监控 |
| Grafana | 3001 | 指标仪表盘 |
| Prometheus | 9090 | 指标采集 |
| PostgreSQL | 5432 | 主数据库 |
| Redis | 6379 | 缓存/消息队列 |
| ChromaDB | 8001 | 知识库向量库 |
| Milvus | 19530 | 缺陷知识库 |
| OmniParser | 7861 | 视觉识别 |
| Locust | 8089 | 性能测试 |

### 缩放 Workers

```bash
# 增加 UI Worker 数量
docker-compose up -d --scale worker-ui=4

# 增加 API Worker 数量
docker-compose up -d --scale worker-api=8
```

---

## ☸️ Kubernetes 部署

### 前置条件

- Kubernetes 1.25+
- kubectl 已配置
- StorageClass: standard (或修改 YAML)
- NVIDIA GPU Operator (OmniParser 需要)

### 部署步骤

```bash
# 1. 创建命名空间
kubectl apply -f kubernetes/chongming.yaml

# 2. 创建 Secrets (需先编辑)
kubectl create secret generic chongming-secrets \
  --namespace=chongming \
  --from-literal=DATABASE_PASSWORD=chongming123 \
  --from-literal=QWEN_API_KEY=your_api_key

# 3. 部署所有资源
kubectl apply -f kubernetes/chongming.yaml

# 4. 检查 Pod 状态
kubectl get pods -n chongming

# 5. 检查 Service
kubectl get svc -n chongming
```

### Ingress 配置

需要配置 DNS 指向 Ingress Controller：
- `chongming.example.com` → Frontend
- `api.chongming.example.com` → API Gateway

### HPA 自动扩缩容

已配置的 HPA：
- `api-gateway`: 2-10 Pod, CPU 70%
- `worker-ui`: 1-5 Pod, CPU 80%
- `worker-api`: 2-10 Pod, CPU 70%

---

## 📊 OpenAPI 文档

### Swagger UI 预览

```bash
# 使用 Docker 运行 Swagger UI
docker run -p 8080:8080 \
  -e SWAGGER_JSON=/openapi.yaml \
  -v $(pwd)/openapi.yaml:/openapi.yaml \
  swaggerapi/swagger-ui
```

访问: http://localhost:8080

### 生成客户端 SDK

```bash
# Python SDK
openapi-generator-cli generate \
  -i openapi.yaml \
  -g python \
  -o ./sdk/python

# TypeScript SDK
openapi-generator-cli generate \
  -i openapi.yaml \
  -g typescript-fetch \
  -o ./sdk/typescript
```

---

## 🔐 安全配置

### 生产环境检查清单

- [ ] 修改所有默认密码
- [ ] 配置 SSL/TLS 证书
- [ ] 启用 Kubernetes NetworkPolicy
- [ ] 配置 CORS 白名单
- [ ] 启用 API 速率限制
- [ ] 配置日志收集 (ELK/Loki)

---

## 📈 监控

### Grafana 仪表盘

- API 请求延迟
- Celery 队列深度
- Worker 健康状态
- 数据库连接池
- Redis 内存使用

### 告警规则

配置在 `prometheus.yml` 中，可对接:
- Slack
- 钉钉
- 邮件

---

## 🔧 故障排查

```bash
# 查看 API 日志
docker-compose logs -f api-gateway

# 查看 Worker 日志
docker-compose logs -f worker-ui worker-api

# 进入容器调试
docker-compose exec api-gateway /bin/bash

# Kubernetes 调试
kubectl logs -f deployment/api-gateway -n chongming
kubectl exec -it deployment/api-gateway -n chongming -- /bin/bash
```

---

## 📞 支持

- GitHub Issues: https://github.com/your-org/chongming/issues
- 文档: https://docs.chongming.ai
