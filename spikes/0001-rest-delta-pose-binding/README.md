# Spike 0001 — Rest-delta pose binding

## Pergunta

Uma ligação não destrutiva entre dois rigs com rests diferentes pode copiar
quaternions locais, ou precisa converter a matriz de pose pelo delta entre os
rests e pela cadeia de pais?

## Fixture

`pipeline/rest_delta_fixture.py` cria em memória uma armature de origem e duas
armatures de destino, cada uma com uma cadeia de dois ossos. As rests têm eixos
deliberadamente distintos. A origem recebe rotações locais no pai e no filho.

O experimento mede duas alternativas:

1. **Cópia local ingênua:** aplica os mesmos quaternions da origem no destino.
2. **Delta de rest como rotação local:** para cada osso, calcula `pose @
   source_rest^-1 @ target_rest`, transforma o resultado para o espaço local
   do destino com `Object.convert_space`, e aplica seus componentes. Esta é a
   etapa de conversão usada pelo Rigify para preservar a diferença entre rests.
3. **Delta de rest como matriz de pose:** aplica a matriz convertida diretamente
   no osso de destino. Esta é a referência para verificar se a representação
   limitada a componentes locais preserva a cadeia.

O pipeline falha se a matriz de pose de referência não reproduzir o resultado
esperado ou se a cópia ingênua não divergir na fixture. O resultado separa o
erro da aplicação por componentes locais do erro da transformação de rest. Ele
é escrito em `eval/result.json`; esse arquivo é evidência descartável e não é
um asset de personagem.

Como PoseCap é pelvis-locked, a aprovação mede apenas a orientação 3D de cada
junta. A posição do filho conectado é registrada separadamente: Blender a
preserva a partir da cadeia e ela não é uma entrada do contrato de pose atual.

Por fim, a fixture repete a mesma rotação local do filho com duas rotações
distintas do pai. A rotação convertida do filho precisa permanecer a mesma;
isso demonstra que a compensação pode ser pré-calculada por osso, em vez de
depender do frame anterior do pai.

Também verifica a forma que o `core` consome: a compensação é a diferença entre
as orientações de rest acumuladas na cadeia, na ordem `target_rest^-1 @
source_rest`; a rotação mapeada é `compensation @ source @
compensation^-1`.

## Como executar

```powershell
C:\Dev\PoseCap\.agentic\tools\blender-5.2.0-windows-x64\blender.exe --background --factory-startup --python spikes\0001-rest-delta-pose-binding\pipeline\rest_delta_fixture.py
```

## Limite do experimento

Ele valida a transformação de rest e de cadeia no Blender, sem qualquer
modelo SMPL-X nem dados licenciados. A produção só pode adotar a técnica após
traduzir esse resultado para uma API testável no `core` e integrar a construção
do mapa no boundary do addon.
