-- Maps external .dat identifiers (FND.../AST...) to internal
-- Faker-generated identifiers (FUND_.../PORT_...) for reconciliation.
-- Safe to re-run: creates schema/tables only if missing, seeds only if empty.

-- Create the staging schema if it doesn't exist yet
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'staging')
BEGIN
    EXEC('CREATE SCHEMA staging');
END

-- Fund crosswalk
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'fund_id_mapping' AND schema_id = SCHEMA_ID('staging'))
BEGIN
    CREATE TABLE staging.fund_id_mapping (
        external_fund_id   VARCHAR(20) PRIMARY KEY,
        internal_fund_id   VARCHAR(20) NOT NULL      
    );
END

IF NOT EXISTS (SELECT 1 FROM staging.fund_id_mapping)
BEGIN
    INSERT INTO staging.fund_id_mapping (external_fund_id, internal_fund_id)
    VALUES
        ('FND001', 'FUND_001'),
        ('FND002', 'FUND_002'),
        ('FND003', 'FUND_003');
END

-- Asset / portfolio company crosswalk
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'asset_id_mapping' AND schema_id = SCHEMA_ID('staging'))
BEGIN
    CREATE TABLE staging.asset_id_mapping (
        external_asset_id    VARCHAR(20) PRIMARY KEY,
        external_asset_name  VARCHAR(200),             
        internal_company_id  VARCHAR(20) NOT NULL        
    );
END

IF NOT EXISTS (SELECT 1 FROM staging.asset_id_mapping)
BEGIN
    INSERT INTO staging.asset_id_mapping (external_asset_id, external_asset_name, internal_company_id)
    VALUES
        ('AST001', 'ALPHACO',     'PORT_0001'),
        ('AST002', 'BETATECH',    'PORT_0002'),
        ('AST003', 'GAMMAIND',    'PORT_0003'),
        ('AST004', 'DELTAENERGY', 'PORT_0004'),
        ('AST005', 'EPSILONHC',   'PORT_0005'),
        ('AST006', 'ZETALOG',     'PORT_0006'),
        ('AST007', 'THETAMOB',    'PORT_0007');   
END
