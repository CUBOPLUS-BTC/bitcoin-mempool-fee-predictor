# 🔒 Security Hardening v2.1.1

## Resumen de Mejoras de Seguridad

Esta versión implementa mejoras de seguridad adicionales recomendadas por el análisis de pentest post-patch:

### 1. Ocultar Swagger/ReDoc en Producción (MEDIA-R01)

**Problema:** La API exponía `/docs` y `/redoc` en producción, revelando la superficie de ataque.

**Solución:** Documentación condicional basada en entorno.

```python
# api/main.py
ENV = os.getenv("ENV", "development")
DOCS_URL = "/docs" if ENV != "production" else None
REDOC_URL = "/redoc" if ENV != "production" else None

app = FastAPI(
    docs_url=DOCS_URL,
    redoc_url=REDOC_URL,
    openapi_url="/openapi.json" if ENV != "production" else None,
)
```

**Comportamiento:**
- Desarrollo: Documentación disponible en `/docs` y `/redoc`
- Producción: Endpoints de documentación devuelven 404

---

### 2. Multi-Tenant API Key Management (A01:2021)

**Problema:** API key estática única - punto único de fallo.

**Solución:** Sistema de múltiples API keys con Redis caching.

**Archivo:** `api/multi_key_auth.py`

#### Características:

| Feature | Descripción |
|---------|-------------|
| Multi-tenant | Múltiples clientes con keys independientes |
| Redis Cache | Alta performance con TTL automático |
| Per-client Rate Limit | Límites configurables por cliente |
| Key Revocation | Revocación inmediata sin afectar otros clientes |
| Key Rotation | Rotación automática de keys |

#### Configuración:

```bash
# Redis connection
export REDIS_URL="redis://localhost:6379/0"

# Master API key (legacy support)
export API_KEY="your-master-key"

# Cache TTL (seconds)
export API_KEY_CACHE_TTL="3600"
```

#### Uso B2B:

```python
# Crear API key para nuevo cliente
from api.multi_key_auth import auth_manager

api_key, info = auth_manager.create_api_key(
    client_name="exchange_client_001",
    permissions=["read"],
    rate_limit=100,  # 100 req/min
    expires_days=90
)

print(f"New API Key: {api_key}")  # Entregar al cliente
print(f"Key ID: {info.key_id}")   # Para administración
```

#### Revocación:

```python
# Revocar key comprometida
auth_manager.revoke_api_key("key_abc123")
# Solo afecta ese cliente, otros continúan operando
```

---

### 3. Cifrado de Datos en Reposo (A02:2021)

**Problema:** Snapshots y archivos .parquet almacenados en texto plano.

**Solución:** Cifrado Fernet (AES-128-CBC con HMAC) para datos sensibles.

**Archivo:** `src/data_encryption.py`

#### Características:

- **Algoritmo:** Fernet (AES-128-CBC + HMAC-SHA256)
- **Key Derivation:** PBKDF2-HMAC-SHA256 con 100k iterations
- **Extensión:** `.encrypted` automática
- **Metadata:** Header JSON con información de versión

#### Uso CLI:

```bash
# Cifrar directorio de snapshots
export DATA_ENCRYPTION_KEY="your-secure-password"
python src/data_encryption.py encrypt --dir data/processed

# Descifrar
python src/data_encryption.py decrypt --dir data/processed

# Estado
python src/data_encryption.py status --dir data/processed
```

#### Uso Programático:

```python
from src.data_encryption import DataEncryptionManager

# Inicializar
manager = DataEncryptionManager(password="secret-key")

# Cifrar archivo
encrypted_path = manager.encrypt_file("data/processed/snapshots_2026.parquet")
# Resultado: snapshots_2026.parquet.encrypted

# Descifrar
decrypted_path = manager.decrypt_file("snapshots_2026.parquet.encrypted")

# Cifrar directorio completo
manager.encrypt_directory("data/processed", pattern="*.parquet")

# Rotación de claves
manager.rotate_key("data/processed", new_password="new-secret")
```

#### Integración con Ingesta:

```python
# En ingestion.py - guardar snapshots cifrados
from src.data_encryption import encryption_manager

# Automáticamente cifra si DATA_ENCRYPTION_KEY está configurado
ingestion.save_snapshot(snapshot, encrypt=True)

# Lee descifrando automáticamente
data = ingestion.load_snapshots(encrypted=True)
```

---

## Configuración de Producción

### Variables de Entorno

```bash
# Entorno
export ENV="production"

# Seguridad: Ocultar docs
export API_KEY="master-api-key-for-backward-compat"

# Multi-key auth con Redis
export REDIS_URL="redis://redis.internal:6379/0"

# Cifrado de datos
export DATA_ENCRYPTION_KEY="32-char-secure-password-here!!"

# Rate limiting (opcional con Redis)
export API_KEY_CACHE_TTL="3600"
```

### Docker Compose (Redis)

```yaml
services:
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    
  api:
    environment:
      - REDIS_URL=redis://redis:6379/0
      - DATA_ENCRYPTION_KEY=${DATA_ENCRYPTION_KEY}
    depends_on:
      - redis
```

---

## Testing de Seguridad

### Verificar Docs Ocultos

```bash
# En desarrollo (200 OK)
curl http://localhost:8000/docs

# En producción (404 Not Found)
ENV=production python -m uvicorn api.main:app
curl http://localhost:8000/docs  # Debe devolver 404
```

### Testing Multi-Key

```bash
# Sin key (401)
curl http://localhost:8000/fees/predict

# Con key inválida (401)
curl -H "X-API-Key: invalid" http://localhost:8000/fees/predict

# Con key válida (200)
curl -H "X-API-Key: dev-test-key" http://localhost:8000/fees/predict
```

### Testing Cifrado

```bash
# Crear archivo de prueba
echo "test data" > /tmp/test.parquet

# Cifrar
python -c "
from src.data_encryption import DataEncryptionManager
m = DataEncryptionManager('secret')
m.encrypt_file('/tmp/test.parquet')
"

# Verificar que existe .encrypted
ls -la /tmp/test.parquet*

# Descifrar
python -c "
from src.data_encryption import DataEncryptionManager
m = DataEncryptionManager('secret')
m.decrypt_file('/tmp/test.parquet.encrypted')
"
```

---

## Compliance & Seguridad

| Requisito | Implementación | Status |
|-----------|----------------|--------|
| MEDIA-R01 | Docs ocultos en prod | ✅ |
| A01:2021 | Multi-tenant API keys | ✅ |
| A02:2021 | Cifrado Fernet | ✅ |
| A05:2021 | Redis security config | ✅ |
| A07:2021 | Logging de intentos fallidos | ✅ |

---

## Próximos Pasos Recomendados

1. **Implementar key escrow** para recuperación de datos cifrados
2. **HSM integration** para protección de claves maestras
3. **Audit logging** centralizado para todas las operaciones de auth
4. **Certificate pinning** para conexiones Redis TLS

---

*Versión: 2.1.1*  
*Actualizado: 2026-04-18*
