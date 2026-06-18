# Catalogo de Errores

Este archivo define un catalogo base de errores para el sistema de archivos.
La idea es que cada error visible al usuario tenga un codigo estable del tipo
`ERROR ###`, para que soporte y operacion puedan identificarlo rapido.

Formato sugerido en la aplicacion:

- `PDF no encontrado - ERROR 421`
- `No tienes permiso para eliminar archivos - ERROR 203`
- `No se pudo unir el PDF - ERROR 423`

Notas:

- Este catalogo cubre los errores actuales y los escenarios operativos mas probables del sistema.
- No existe un "100% de todos los errores posibles" a nivel tecnico absoluto, pero este listado sirve como base real para soporte.
- Los codigos deben mantenerse estables en el tiempo.

## 001-099 Sesion y autenticacion

| Codigo | Error | Mensaje sugerido | Causa probable | Que revisar |
|---|---|---|---|---|
| 001 | Sesion invalida | Sesion invalida. Recarga e intenta de nuevo. - ERROR 001 | CSRF vencido o sesion inconsistente | Cookie de sesion, token CSRF, reinicio de navegador |
| 002 | Contrasena incorrecta | Contrasena incorrecta. - ERROR 002 | Password no coincide con el hash guardado | Usuario correcto, hash en base de datos |
| 003 | Usuario no registrado | Usuario no registrado. - ERROR 003 | Usuario inexistente o inactivo | Tabla `usuarios`, columna `activo` |
| 004 | Login requerido | Debes iniciar sesion para continuar. - ERROR 004 | Ruta protegida sin sesion | Login y sesion activa |
| 005 | Usuario inactivo | El usuario esta inactivo. - ERROR 005 | `activo = 0` | Registro en `usuarios` |

## 100-149 Conexion y configuracion

| Codigo | Error | Mensaje sugerido | Causa probable | Que revisar |
|---|---|---|---|---|
| 100 | DATABASE_URL ausente | Configuracion de base de datos incompleta. - ERROR 100 | Variable no definida en entorno o `systemd` | `DATABASE_URL`, `systemctl show ... --property=Environment` |
| 101 | DATABASE_URL sin base de datos | Configuracion de base de datos invalida. - ERROR 101 | URL sin nombre de DB | Valor de `DATABASE_URL` |
| 102 | Esquema de DB invalido | Configuracion de conexion no soportada. - ERROR 102 | URL no usa `sqlserver://` o `mssql://` | `DATABASE_URL` |
| 103 | Login SQL fallido | No se pudo autenticar contra la base de datos. - ERROR 103 | Usuario SQL o password incorrecta | Login SQL, `pyodbc`, password real |
| 104 | Driver ODBC ausente | No se encontro el driver de SQL Server. - ERROR 104 | `pyodbc` o driver ODBC no instalado | `pip show pyodbc`, `odbcinst -q -d` |
| 105 | Servidor SQL no accesible | No se pudo conectar al servidor SQL. - ERROR 105 | SQL Server apagado o puerto cerrado | `systemctl status mssql-server`, `ss -ltnp | grep 1433` |
| 106 | Dependencia faltante | Falta una dependencia del sistema. - ERROR 106 | Modulo Python no instalado | `pip install -r requirements` o paquete puntual |

## 200-249 Permisos y autorizacion

| Codigo | Error | Mensaje sugerido | Causa probable | Que revisar |
|---|---|---|---|---|
| 200 | Accion no permitida | Accion no permitida. - ERROR 200 | Flujo no autorizado para el rol actual | Rol en sesion |
| 201 | Sin permiso para modificar usuarios | No tienes permiso para modificar usuarios. - ERROR 201 | Usuario no admin | Rol `admin` |
| 202 | Sin permiso sobre empresa | No tienes permiso para esa empresa. - ERROR 202 | Usuario fuera de la empresa activa | `usuariosempresas`, empresa en sesion |
| 203 | Sin permiso para eliminar archivos | No tienes permiso para eliminar archivos en esta empresa. - ERROR 203 | Permiso `eliminar = 0` | `usuariosempresas.eliminar` |
| 204 | Sin permiso para modificar cajas | No tienes permiso para modificar cajas. - ERROR 204 | Rol insuficiente | Rol o permisos de empresa |
| 205 | Sin permiso para crear cajas | No tienes permiso para crear cajas. - ERROR 205 | Rol insuficiente | Rol o permisos de empresa |
| 206 | Acceso denegado a modulo admin | Acceso denegado. - ERROR 206 | Usuario sin rol admin/supervisor | Rol actual |
| 207 | No puedes eliminar tu propio usuario | No puedes eliminar tu propio usuario. - ERROR 207 | Proteccion de cuenta actual | Usuario logueado |
| 208 | No puedes mover elementos al Archivador | No puedes mover elementos al Archivador. - ERROR 208 | Restriccion funcional del archivador | Empresa destino |

## 300-349 Usuarios y empresas

| Codigo | Error | Mensaje sugerido | Causa probable | Que revisar |
|---|---|---|---|---|
| 300 | Nombre de empresa vacio | Debes ingresar un nombre de empresa. - ERROR 300 | Formulario vacio | Campo nombre |
| 301 | Usuario no existe | El usuario no existe. - ERROR 301 | Nombre de usuario mal escrito o no creado | Tabla `usuarios` |
| 302 | Usuario ya existe | El usuario ya existe. - ERROR 302 | Duplicado por `usuario` | Registro existente |
| 303 | Usuario y contrasena obligatorios | Usuario y contrasena son obligatorios. - ERROR 303 | Formulario incompleto | Campos obligatorios |
| 304 | Error al crear usuario | No se pudo crear el usuario. - ERROR 304 | Restriccion SQL, dato invalido, login roto | Traceback, inserts en `usuarios` |
| 305 | Error al actualizar usuario | No se pudo actualizar el usuario. - ERROR 305 | Dato invalido o conflicto SQL | Query de update |
| 306 | Error al eliminar usuario | No se pudo eliminar el usuario. - ERROR 306 | FK, datos dependientes o estrategia de borrado | `usuariosempresas`, `usuariosregistrados`, `empresas` |
| 307 | Grupo o empresa no existe | La empresa no existe. - ERROR 307 | ID inexistente o archivado | Tabla `empresas` |
| 308 | Empresa archivada | La empresa esta archivada. - ERROR 308 | Contexto desactualizado | Empresa en sesion |

## 350-399 Cajas

| Codigo | Error | Mensaje sugerido | Causa probable | Que revisar |
|---|---|---|---|---|
| 350 | Caja no existe | La caja no existe. - ERROR 350 | ID incorrecto o caja eliminada | Tabla `cajas` |
| 351 | Caja pendiente no movible | La caja pendiente no se puede mover. - ERROR 351 | Intento de mover Caja 0 como caja normal | Seleccion del archivador |
| 352 | Solapamiento de rangos | La caja tiene solapamiento de rango en destino. - ERROR 352 | Rango ya ocupado en la empresa destino | Rangos de `cajas` |
| 353 | No se puede crear caja | No se pudo crear la caja. - ERROR 353 | Restriccion SQL o rango invalido | Insert de `cajas` |
| 354 | No se puede modificar caja | No se pudo modificar la caja. - ERROR 354 | Conflicto de rango o SQL | Rangos y empresa |
| 355 | No se puede eliminar caja | No se pudo eliminar la caja. - ERROR 355 | Restriccion o fallo al reubicar archivos | Caja pendiente, archivos relacionados |

## 400-499 Archivos y PDF

| Codigo | Error | Mensaje sugerido | Causa probable | Que revisar |
|---|---|---|---|---|
| 400 | Tipo de documento invalido | Tipo de documento invalido. - ERROR 400 | Valor fuera de `CC/CE/TI/RC` | Campo `tipo_doc` |
| 401 | Documento invalido | Documento invalido. - ERROR 401 | Numero vacio, texto, cero o formato no valido | Valor de `numero` |
| 402 | Nombre obligatorio | El nombre es obligatorio. - ERROR 402 | Campo nombre vacio | Formulario |
| 403 | No existe caja para el documento | No existe una caja cuyo rango contenga ese documento. - ERROR 403 | Numero fuera de todo rango | Rangos de `cajas` |
| 404 | Archivo no encontrado para modificar | No se encontro el archivo a modificar. - ERROR 404 | Registro inexistente o inconsistente | Tabla `archivos` |
| 405 | Archivo no encontrado para eliminar | No se encontro el archivo a eliminar. - ERROR 405 | ID/numero inexistente | Tabla `archivos` |
| 406 | Archivo duplicado | Ya existe un documento con ese numero en la empresa. - ERROR 406 | Indice unico por empresa + numero | `archivos_grupo_numero_idx` |
| 407 | El archivo debe ser PDF | El archivo debe ser PDF. - ERROR 407 | Archivo con extension o MIME incorrecto | Archivo subido |
| 408 | Error al guardar PDF | No se pudo guardar el PDF. - ERROR 408 | Permisos, ruta invalida o fallo de escritura | Carpeta `uploads/pdfs` |
| 409 | Error al modificar archivo | No se pudo modificar el archivo. - ERROR 409 | Conflicto SQL, PDF, numero duplicado | Update real |
| 410 | Error al eliminar archivo | No se pudo eliminar el archivo. - ERROR 410 | FK, PDF, borrado parcial | Delete y logs |
| 411 | Documento agregado correctamente pero con warning | El documento fue creado con observaciones. - ERROR 411 | Caso de negocio especial | Revisar log puntual |
| 420 | PDF no asociado | Este documento no tiene PDF. - ERROR 420 | `pdf_path` nulo | Tabla `archivos` |
| 421 | PDF no encontrado en servidor | PDF no encontrado. - ERROR 421 | Registro apunta a archivo inexistente | `pdf_path`, disco del servidor |
| 422 | Seleccion PDF invalida | La seleccion de PDFs no es valida. - ERROR 422 | IDs malformados o vacios | Payload del modal |
| 423 | No se pudo unir el PDF | No se pudo unir el PDF. - ERROR 423 | PDF corrupto, fallo al combinar, archivo faltante | Fuente y destino PDF |
| 424 | No se encontraron PDFs para descargar | No se encontraron PDFs para la seleccion indicada. - ERROR 424 | Todos sin PDF o IDs invalidos | Seleccion real |
| 425 | PDFs no disponibles en servidor | Los PDFs seleccionados no estan disponibles en el servidor. - ERROR 425 | Faltan archivos fisicos | Disco del servidor |

## 500-549 Excel e importacion

| Codigo | Error | Mensaje sugerido | Causa probable | Que revisar |
|---|---|---|---|---|
| 500 | Excel no seleccionado | Debes seleccionar un archivo Excel. - ERROR 500 | Formulario sin archivo | Input `excel` |
| 501 | Excel invalido | El archivo Excel es invalido. - ERROR 501 | Archivo corrupto o extension falsa | `load_workbook` |
| 502 | Formato Excel no compatible | El formato del Excel no es compatible. - ERROR 502 | Headers distintos al esperado | Encabezados `tipo_doc`, `documento`, etc. |
| 503 | Importacion parcial | La importacion se completo con omisiones. - ERROR 503 | Filas invalidas, duplicadas o fuera de rango | Resultado del job |
| 504 | Error de importacion Excel | No se pudo completar la importacion Excel. - ERROR 504 | Excepcion dentro del hilo | Journal y traceback |
| 505 | Exportacion Excel fallida | No se pudo generar el Excel. - ERROR 505 | Error de consulta o de `openpyxl` | Query y memoria |

## 550-599 Duplicados

| Codigo | Error | Mensaje sugerido | Causa probable | Que revisar |
|---|---|---|---|---|
| 550 | No seleccionaste registros | No seleccionaste registros. - ERROR 550 | Nada marcado | Seleccion UI |
| 551 | Debes seleccionar al menos 2 registros | Debes seleccionar al menos 2 registros. - ERROR 551 | Seleccion insuficiente | Lista marcada |
| 552 | Falta registro base | Selecciona el registro base. - ERROR 552 | No se eligio base para unificar | `base_id` |
| 553 | Registro base fuera de seleccion | El registro base debe estar dentro de la seleccion. - ERROR 553 | Seleccion inconsistente | IDs enviados |
| 554 | Seleccion invalida | Seleccion invalida. - ERROR 554 | IDs inexistentes o ajenos a la empresa | Base de datos |
| 555 | Error al unificar duplicados | Error al unificar duplicados. - ERROR 555 | Update/delete fallido | Journal y SQL |

## 600-679 Archivador y movimientos masivos

| Codigo | Error | Mensaje sugerido | Causa probable | Que revisar |
|---|---|---|---|---|
| 600 | No hay elementos seleccionados | No hay elementos seleccionados. - ERROR 600 | Nada marcado en archivador | Seleccion UI |
| 601 | Metodo no permitido en archivador | Acceso invalido al modulo de archivador. - ERROR 601 | GET/refresh a endpoint POST | Ruta de transferencia o eliminacion |
| 602 | Error moviendo elementos | No se pudieron mover los elementos. - ERROR 602 | Excepcion SQL o timeout operativo | `archivador_transferir` |
| 603 | Error eliminando seleccion | No se pudieron eliminar los elementos seleccionados. - ERROR 603 | Borrado masivo parcial o SQL | `archivador_eliminar` |
| 604 | Caja pendiente no se movio | La caja pendiente no se movio. - ERROR 604 | Proteccion funcional | Caja 0 |
| 605 | Reasignacion a caja pendiente | Algunos documentos se movieron a la caja pendiente. - ERROR 605 | No existia rango destino | Caja 0 destino |

## 680-749 Logs, auditoria y deshacer

| Codigo | Error | Mensaje sugerido | Causa probable | Que revisar |
|---|---|---|---|---|
| 680 | No se pudo cargar Auditoria | No se pudo cargar Auditoria. - ERROR 680 | Query rota o esquema incompleto | Tabla `auditoria` |
| 681 | No se pudo cargar Movimientos | No se pudo cargar Movimientos. - ERROR 681 | Query rota o esquema incompleto | Tabla `movimientos` |
| 682 | No se pudo cargar Usuarios | No se pudo cargar Usuarios. - ERROR 682 | Query rota o esquema incompleto | Tabla `usuariosregistrados` |
| 683 | Movimiento no encontrado | Movimiento no encontrado. - ERROR 683 | ID inexistente | Tabla `movimientos` |
| 684 | Error al deshacer movimiento | No se pudo deshacer el movimiento. - ERROR 684 | Datos previos incompletos, FK o identity | `antes`, `despues`, estructura SQL |

## 750-799 Rutas y navegacion

| Codigo | Error | Mensaje sugerido | Causa probable | Que revisar |
|---|---|---|---|---|
| 750 | Ruta no encontrada | Recurso no encontrado. - ERROR 750 | URL invalida | Ruta usada |
| 751 | Metodo no permitido | Metodo no permitido. - ERROR 751 | GET/POST incorrecto | Formulario o endpoint |

## 900-999 Errores internos

| Codigo | Error | Mensaje sugerido | Causa probable | Que revisar |
|---|---|---|---|---|
| 900 | Error interno generico | Ocurrio un error interno. Intenta de nuevo. - ERROR 900 | Excepcion no controlada | Journal, traceback |
| 901 | Error de integridad SQL | No se pudo guardar la informacion por conflicto de datos. - ERROR 901 | UNIQUE, FK, NULL, truncamiento | Mensaje exacto de SQL Server |
| 902 | Error de datos truncados | Un texto excede el tamano permitido. - ERROR 902 | Columnas muy cortas | Tamano de columnas |
| 903 | Error de columna faltante | La estructura de la base de datos no coincide con la aplicacion. - ERROR 903 | Migracion incompleta | Esquema real |
| 904 | Error de archivo en disco | No se pudo acceder a un archivo del servidor. - ERROR 904 | Permisos o ruta inexistente | `uploads`, PDFs, imports |

## Recomendacion de uso en la app

1. Nunca mostrar solo "Ocurrio un error".
2. Mostrar siempre `mensaje legible + ERROR ###`.
3. Mantener en logs:
   - codigo
   - usuario
   - empresa
   - accion
   - detalle tecnico
4. Para soporte, pedirle al cliente:
   - captura
   - codigo de error
   - hora aproximada
   - empresa y usuario

## Siguiente fase recomendada

La siguiente mejora natural es centralizar esto en codigo, por ejemplo con:

- `error_catalog.py`
- helper `error_ui(421, "PDF no encontrado")`
- flashes y respuestas HTTP usando codigos oficiales del catalogo

Asi el sistema deja de depender de mensajes sueltos escritos a mano.
