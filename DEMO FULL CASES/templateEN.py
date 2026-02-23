import xlsxwriter

def create_excel_template_en():
    # 1. Crear el archivo Excel con el nuevo nombre
    workbook = xlsxwriter.Workbook('STIBO_AI_Onboarding_Template_[en].xlsx')

    # ==========================================
    # 2. DEFINIR COLORES Y ESTILOS
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
        'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True
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
    # HOJA 1: Prerrequisitos de Atributos (MDM) - INGLÉS
    # ==========================================
    ws1 = workbook.add_worksheet('1. Attribute Prerequisites')
    
    # Ajustar ancho de columnas
    ws1.set_column('B:B', 25)
    ws1.set_column('C:C', 30)
    ws1.set_column('D:D', 30)
    ws1.set_column('E:E', 25)
    ws1.set_column('F:F', 35)

    # Textos Intro
    ws1.write('B2', 'Integration Guide: AI for eCommerce', formato_titulo)
    ws1.write('B4', 'PHASE 1: Data Model Preparation in STEP', formato_subtitulo)
    ws1.write('B6', 'Create the following attributes at the Product level (Golden Record) to receive the AI-generated content:', formato_celda_normal)

    # Headers de la tabla
    headers_attr = ['Content Type', 'Recommended Name', 'Recommended ID (Suggestion)', 'Validation / STEP Type', 'Dependency']
    for col, texto in enumerate(headers_attr):
        ws1.write(7, col + 1, texto, formato_header_tabla)

    # Datos de la tabla
    datos_attr = [
        ['eCommerce Name', 'AI Web Name', 'AI.PR.WebName', 'Text (Max 120 chars)', 'Dimension (Language/Country) *'],
        ['Short Description', 'AI Short Description', 'AI.PR.WebShortDescription', 'Text (Max 250 chars)', 'Dimension (Language/Country) *'],
        ['Long Description', 'AI Long Description', 'AI.PR.WebLongDescription', 'Text (No limit / HTML)', 'Dimension (Language/Country) *']
    ]

    for row_idx, row_data in enumerate(datos_attr):
        for col_idx, cell_data in enumerate(row_data):
            if col_idx == 2: # El ID centrado
                ws1.write(row_idx + 8, col_idx + 1, cell_data, formato_celda_centro)
            else:
                ws1.write(row_idx + 8, col_idx + 1, cell_data, formato_celda_normal)

    # Nota importante
    nota = ("🌍 Crucial note on Translations: If you plan to use automated translation to multiple languages, "
            "it is strictly necessary that these 3 attributes are dimension-dependent (Dimension Dependent) "
            "in your data model to avoid overwriting the original language content.")
    ws1.merge_range('B13:F14', nota, formato_alerta)


    # ==========================================
    # HOJA 2: Templates de Exportación XML - INGLÉS
    # ==========================================
    ws2 = workbook.add_worksheet('2. STEPXML Export')
    
    ws2.set_column('B:B', 25)
    ws2.set_column('C:C', 100) # Columna ancha para el código XML

    ws2.write('B2', 'Data Export Templates', formato_titulo)
    ws2.write('B4', 'PHASE 2: Export Manager Configuration', formato_subtitulo)

    # Instrucción 1
    ws2.write('B6', 'Export Type', formato_header_tabla)
    ws2.write('C6', '1. Product Sample Data', formato_header_tabla)
    ws2.write('B7', 'Purpose', formato_celda_normal)
    ws2.write('C7', 'Extract technical attributes, LOVs, and Assets to provide accurate context to the AI.', formato_celda_normal)
    
    ws2.write('B8', 'XML Template Code\n(Paste in STEP)', formato_header_tabla)
    
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
    ws2.write('B10', 'Export Type', formato_header_tabla)
    ws2.write('C10', '2. Product Hierarchy (PPH Sample Data)', formato_header_tabla)
    ws2.write('B11', 'Purpose', formato_celda_normal)
    ws2.write('C11', 'Extract the category tree (Entities) to provide SEO and hierarchical context.', formato_celda_normal)
    
    ws2.write('B12', 'XML Template Code\n(Paste in STEP)', formato_header_tabla)
    
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
    print("✅ File 'STIBO_AI_Onboarding_Template_[en].xlsx' successfully generated. Ready to share!")

if __name__ == "__main__":
    create_excel_template_en()