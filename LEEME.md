# Ventanilla de consulta SAT

Alertas tempranas de bloqueo, pregrado Sede Medellín, periodo 2026-2S. Usa el Kit UNAL (CDN 12112024, tema main). Es una aplicación estática: no necesita base de datos ni servidor de aplicaciones.

Pestañas: Nivel de riesgo por estudiante, Nivel de riesgo por asignatura, Asignaturas en riesgo por pérdida, Consulta individual e Información del estudiante.

## Contenido

| Ruta | Para qué sirve |
|---|---|
| `index.html` | Página de entrada |
| `css/tablero.css` | Estilos |
| `js/app.jsx` | Aplicación (React, se transpila en el navegador) |
| `vendor/` | React, ReactDOM, Babel y Apache ECharts (sin depender de internet) |
| `datos/sat_*.js` | Datos del periodo (ver abajo) |
| `scripts/` | Solo para actualizar datos (`etl_ventanilla.py`, `servir.py` y `modelo/` con el cálculo del riesgo); no hace falta publicarlos |

El Kit UNAL (estilos, íconos y escudo) se carga desde `gestionapp.unal.edu.co` y `gestionapp.medellin.unal.edu.co`; el servidor y los usuarios deben poder llegar a esas direcciones.

## Desplegar

1. Publicar la carpeta completa en cualquier servidor web estático (Apache, Nginx, IIS, el portal institucional). Debe servirse por HTTP o HTTPS; abrir `index.html` con doble clic no funciona.
2. Probar en local: `python3 scripts/servir.py 8765` y abrir `http://localhost:8765`.

## Antes de publicar (obligatorio)

- **El ingreso es provisional.** La función `Ingreso` de `js/app.jsx` compara en el navegador la huella (SHA-256) de un único usuario y contraseña de demostración. No es seguridad real: la huella queda visible en el código y se puede saltar. Hay que reemplazarla por el servicio de autenticación institucional.
- **Los datos no están protegidos.** Los archivos `datos/sat_*.js` contienen documento, nombre, correos, teléfono y dirección de los estudiantes. Cualquiera que conozca la dirección puede descargarlos aunque no inicie sesión. La publicación debe exigir autenticación en el servidor (por ejemplo, acceso restringido a la carpeta `datos/`) y cumplir la Ley 1581 de 2012.

## Actualizar los datos

1. `python3 scripts/modelo/preparar_insumos.py <INSUMOS> <carpeta_de_trabajo>` convierte los insumos (matrícula, bloqueos, notas parciales) y agrega los estudiantes que solo vienen en la matrícula nueva.
2. Ejecutar en ese orden, con la variable `SAT_DATA` apuntando a la carpeta de trabajo: `scripts/modelo/build_dataset.py`, `model_final.py`, `model_notas.py`, `stage2.py` y `final_score.py` (este último también necesita `SAT_EXCEL_ANTERIOR` y `SAT_EXCEL_SALIDA`).
3. `python3 scripts/etl_ventanilla.py <riesgo.xlsx> <notas_2026-2S.xlsx|.pkl> datos` regenera `datos/sat_*.js`.

## Reglas de lectura

- Parcial calificado: porcentaje entre 0 y 100 sin incluirlo, con nota. La fila P01 al 100 es el acumulado del SIA y no cuenta.
- Niveles según la probabilidad de pérdida de calidad de estudiante: bajo menor que 5, medio de 5 a menos de 15, alto 15 o más.
- Terapia Ocupacional (PAET) no está incluida: no aparece en la matrícula entregada.
