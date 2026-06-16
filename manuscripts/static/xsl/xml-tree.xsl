<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

  <xsl:output method="html" encoding="UTF-8" indent="yes"/>

  <!-- Raíz: construye la página HTML -->
  <xsl:template match="/">
    <html>
      <head>
        <meta charset="utf-8"/>
        <title>XML Viewer</title>
        <style>
          body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 0; }
          .toolbar { position: sticky; top: 0; padding: 8px 12px; border-bottom: 1px solid #ddd; background: #fafafa; display: flex; gap: 8px; align-items: center; }
          .toolbar button { padding: 6px 10px; border: 1px solid #ccc; background: #fff; cursor: pointer; border-radius: 6px; }
          .tree { padding: 12px; }
          details { margin-left: 16px; }
          details.root { margin-left: 0; }
          summary { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; font-size: 13px; }
          .tag { color: #7a3e9d; }
          .attr { color: #1c6aa8; }
          .aval { color: #14532d; }
          .closing { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; color: #7a3e9d; margin-left: 24px; }
          pre.text { white-space: pre-wrap; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; background: #f6f8fa; border: 1px solid #eee; padding: 6px 8px; border-radius: 6px; margin: 6px 0 6px 24px; }
          .comment, .pi { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; color: #6a737d; margin-left: 24px; }
        </style>
        <script>
          // Expandir / Colapsar todo
          function expandAll() {
            document.querySelectorAll('details').forEach(d => d.open = true);
          }
          function collapseAll() {
            // deja el root abierto para no "perder" todo
            document.querySelectorAll('details:not(.root)').forEach(d => d.open = false);
            document.querySelectorAll('details.root').forEach(d => d.open = true);
          }
          document.addEventListener('DOMContentLoaded', () => {
            const expand = document.getElementById('btn-expand');
            const collapse = document.getElementById('btn-collapse');
            if (expand) expand.addEventListener('click', expandAll);
            if (collapse) collapse.addEventListener('click', collapseAll);
          });
        </script>
      </head>
      <body>
        <div class="toolbar">
          <button id="btn-expand" type="button">Expandir todo</button>
          <button id="btn-collapse" type="button">Colapsar todo</button>
        </div>
        <div class="tree">
          <!-- Marca el elemento raíz con .root y abierto -->
          <xsl:for-each select="node()[1]">
            <details class="root" open="open">
              <summary>
                &lt;<span class="tag"><xsl:value-of select="name()"/></span>
                <xsl:for-each select="@*">
                  &#160;<span class="attr"><xsl:value-of select="name()"/></span>=
                  "<span class="aval"><xsl:value-of select="."/></span>"
                </xsl:for-each>
                &gt;
              </summary>
              <xsl:apply-templates select="node()|comment()|processing-instruction()"/>
              <div class="closing">&lt;/<span class="tag"><xsl:value-of select="name()"/></span>&gt;</div>
            </details>
          </xsl:for-each>
        </div>
      </body>
    </html>
  </xsl:template>

  <!-- Elementos: render recursivo como <details> -->
  <xsl:template match="*">
    <details>
      <summary>
        &lt;<span class="tag"><xsl:value-of select="name()"/></span>
        <xsl:for-each select="@*">
          &#160;<span class="attr"><xsl:value-of select="name()"/></span>=
          "<span class="aval"><xsl:value-of select="."/></span>"
        </xsl:for-each>
        &gt;
      </summary>
      <xsl:apply-templates select="node()|comment()|processing-instruction()"/>
      <div class="closing">&lt;/<span class="tag"><xsl:value-of select="name()"/></span>&gt;</div>
    </details>
  </xsl:template>

  <!-- Texto: omite sólo-espacios; muestra el resto -->
  <xsl:template match="text()">
    <xsl:variable name="t" select="normalize-space(.)"/>
    <xsl:if test="$t != ''">
      <pre class="text"><xsl:value-of select="."/></pre>
    </xsl:if>
  </xsl:template>

  <!-- Comentarios -->
  <xsl:template match="comment()">
    <div class="comment">&lt;!-- <xsl:value-of select="."/> --&gt;</div>
  </xsl:template>


</xsl:stylesheet>

