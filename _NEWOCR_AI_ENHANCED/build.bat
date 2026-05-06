@echo off
echo Starting Nuitka build...

python -m nuitka ^
    --standalone ^
    --onefile ^
    --follow-imports ^
    --include-data-dir=fonts=fonts ^
    --include-data-dir=image=image ^
    --include-data-dir=chroma_db=chroma_db ^
    --include-data-dir=general_lookup_summary_results=general_lookup_summary_results ^
    --include-data-dir=lookup_summary_results=lookup_summary_results ^
    --include-data-files=.env=.env ^
    --include-data-files=banco_san_vicente_loans.json=banco_san_vicente_loans.json ^
    --include-data-files=lu_risk_settings.json=lu_risk_settings.json ^
    --include-data-files=cibi_prompts.md=cibi_prompts.md ^
    --include-data-files=bsv_logotxt.png=bsv_logotxt.png ^
    --include-data-files=.remember_me=.remember_me ^
    --enable-plugin=tk-inter ^
    --python-flag=no_site,no_warnings ^
    --disable-console ^
    --output-dir=dist ^
    main.py

echo.
echo Build finished! Check the dist folder.
pause