import xlsxwriter

def create_excel_template():
    # 1. Crear el archivo Excel
    workbook = xlsxwriter.Workbook('STIBO_AI_Onboarding_Template.xlsx')

    # ==========================================
    # 2. DEFINIR COLORES Y ESTILOS (El secreto profesional)
    # ==========================================
    formato_titulo = workbook.add_format({
        'bold': True, 'font_size': 16, 'font_color': '#003E71', 
        'valign': 'vcenter'
    })
    
    formato_subtitulo = workbook.add_format({
        'bold': True, 'font_size': 12, 'font_color': '#00959C', 
        'bottom': 1, 'bottom_color': '#00959C'
    })

    formato_header_tabla = workbook.add_format({
        'bold': True, 'bg_color': '#003E71', 'font_color': '#FFFFFF', 
        'border': 1, 'align': 'center', 'valign': 'vcenter'
    })

    formato_celda_normal = workbook.add_format({
        'border': 1, 'valign': 'vcenter', 'text_wrap': True
    })

    formato_celda_centro = workbook.add_format({
        'border': 1, 'valign': 'vcenter', 'align': 'center', 'text_wrap': True
    })

    formato_alerta = workbook.add_format({
        'bg_color': '#E0F2F1', 'font_color': '#003E71', 'italic': True, 
        'border': 1, 'text_wrap': True, 'valign': 'vcenter'
    })

    formato_xml_code = workbook.add_format({
        'font_name': 'Courier New', 'bg_color': '#F0F2F6', 'font_color': '#333333',
        'border': 1, 'text_wrap': True, 'valign': 'top'
    })

    # ==========================================
    # HOJA 1: Prerrequisitos de Atributos (MDM)
    # ==========================================
    ws1 = workbook.add_worksheet('1. Prerrequisitos Atributos')
    
    # Ajustar ancho de columnas
    ws1.set_column('B:B', 25)
    ws1.set_column('C:C', 30)
    ws1.set_column('D:D', 30)
    ws1.set_column('E:E', 25)
    ws1.set_column('F:F', 35)

    # Textos Intro
    ws1.write('B2', 'Guía de Integración: IA para eCommerce', formato_titulo)
    ws1.write('B4', 'FASE 1: Preparación del Modelo de Datos en STEP', formato_subtitulo)
    ws1.write('B6', 'Crear los siguientes atributos a nivel de Producto (Golden Record) para recibir el contenido de la IA:', formato_celda_normal)

    # Headers de la tabla
    headers_attr = ['Tipo de Contenido', 'Nombre Recomendado', 'ID Recomendado (Sugerencia)', 'Validación / Tipo en STEP', 'Dependencia']
    for col, texto in enumerate(headers_attr):
        ws1.write(7, col + 1, texto, formato_header_tabla)

    # Datos de la tabla
    datos_attr = [
        ['Nombre eCommerce', 'AI Web Name', 'AI.PR.WebName', 'Text (Max 120 chars)', 'Dimensión (Idioma/País) *'],
        ['Descripción Corta', 'AI Short Description', 'AI.PR.WebShortDescription', 'Text (Max 250 chars)', 'Dimensión (Idioma/País) *'],
        ['Descripción Larga', 'AI Long Description', 'AI.PR.WebLongDescription', 'Text (No limit / HTML)', 'Dimensión (Idioma/País) *']
    ]

    for row_idx, row_data in enumerate(datos_attr):
        for col_idx, cell_data in enumerate(row_data):
            if col_idx == 2: # El ID centrado
                ws1.write(row_idx + 8, col_idx + 1, cell_data, formato_celda_centro)
            else:
                ws1.write(row_idx + 8, col_idx + 1, cell_data, formato_celda_normal)

    # Nota importante
    nota = ("🌍 Nota crucial sobre Traducciones: Si planea utilizar traducción automatizada a múltiples idiomas, "
            "es estrictamente necesario que estos 3 atributos sean dependientes de dimensión (Dimension Dependent) "
            "en su modelo de datos para no sobrescribir el idioma original.")
    ws1.merge_range('B13:F14', nota, formato_alerta)


    # ==========================================
    # HOJA 2: Templates de Exportación XML
    # ==========================================
    ws2 = workbook.add_worksheet('2. Exportación STEPXML')
    
    ws2.set_column('B:B', 25)
    ws2.set_column('C:C', 100) # Columna ancha para el código XML

    ws2.write('B2', 'Plantillas de Exportación de Datos', formato_titulo)
    ws2.write('B4', 'FASE 2: Configuración del Export Manager', formato_subtitulo)

    # Instrucción 1
    ws2.write('B6', 'Tipo de Exportación', formato_header_tabla)
    ws2.write('C6', '1. Datos de Producto (Product Sample Data)', formato_header_tabla)
    ws2.write('B7', 'Propósito', formato_celda_normal)
    ws2.write('C7', 'Extraer atributos técnicos, LOVs y Assets para dar contexto a la IA.', formato_celda_normal)
    
    ws2.write('B8', 'Código Template XML\n(Pegar en STEP)', formato_header_tabla)
    
    xml_productos = """<STEP-ProductInformation ResolveInlineRefs="true" FollowOverrideSubProducts="true">
    <ListOfValuesGroupList/>
    <ListsOfValues ExportSize="Minimum"/>
    <AttributeList ExportSize="Minimum"/>
    <Assets ExportSize="Minimum">
        <Asset></Asset>
    </Assets>
    <Products ExportSize="Minimum">
        <Product>
            <Name/>
            <AttributeLink/>
            <DataContainerTypeLink/>
            <ClassificationReference IncludeInherited="true"/>
            <ProductCrossReference IncludeInherited="true"/>
            <AssetCrossReference IncludeInherited="true"/>
            <EntityCrossReference IncludeInherited="true"/>
            <ClassificationCrossReference IncludeInherited="true"/>
            <Values IncludeInherited="true"/>
            <OverrideSubProduct/>
            <DataContainers IncludeInherited="true"/>
        </Product>
    </Products>
</STEP-ProductInformation>"""
    ws2.write('C8', xml_productos, formato_xml_code)
    ws2.set_row(7, 350) # Hacer la fila más alta para que quepa el XML

    # Instrucción 2
    ws2.write('B10', 'Tipo de Exportación', formato_header_tabla)
    ws2.write('C10', '2. Jerarquía de Productos (PPH Sample Data)', formato_header_tabla)
    ws2.write('B11', 'Propósito', formato_celda_normal)
    ws2.write('C11', 'Extraer el árbol de categorías (Entities) para contexto SEO.', formato_celda_normal)
    
    ws2.write('B12', 'Código Template XML\n(Pegar en STEP)', formato_header_tabla)
    
    xml_pph = """<STEP-ProductInformation ResolveInlineRefs="true">
    <Entities ExportSize="Minimum">
        <FilterUserType ID="PMDM.PRD.INT.DataSource"/>
        <FilterUserType ID="PMDM.PRD.INT.Level1"/>
        <Entity>
            <Name/><AttributeLink/><ClassificationCrossReference/><Entity/>
            <ProductCrossReference/><AssetCrossReference/><ContextCrossReference/><Values/>
        </Entity>
    </Entities>
    <Products ExportSize="Referenced">
        <FilterUserType ID="PMDM.PRD.INT.Level1"/>
        <Product>
            <Name/><AttributeLink/><ClassificationReference/><Values/>
        </Product>
    </Products>
</STEP-ProductInformation>"""
    ws2.write('C12', xml_pph, formato_xml_code)
    ws2.set_row(11, 280)

    # Cerrar y guardar
    workbook.close()
    print("✅ Archivo 'STIBO_AI_Onboarding_Template.xlsx' generado con éxito. ¡Ábrelo en Excel!")

if __name__ == "__main__":
    create_excel_template()