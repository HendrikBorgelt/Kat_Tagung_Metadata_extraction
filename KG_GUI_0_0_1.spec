# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['KG_GUI_0_0_1.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'rdflib', 'rdflib.namespace', 'rdflib.term', 'rdflib.util',
        'rdflib.collection', 'rdflib.compare', 'rdflib.graph', 'rdflib.plugins',
        'rdflib.plugins.parsers', 'rdflib.plugins.parsers.notation3',
        'rdflib.plugins.serializers', 'rdflib.plugins.serializers.turtle',
        'rdflib.plugins.sparql', 'rdflib.plugins.sparql.processor',
        'rdflib.plugins.sparql.results', 'rdflib.plugins.sparql.parser',
        'tkinter', 'tkinter.ttk', 'tkinter.messagebox', 'tkinter.filedialog'
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='KnowledgeGraphVisualizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # hide console window
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='KnowledgeGraphVisualizer'
)
