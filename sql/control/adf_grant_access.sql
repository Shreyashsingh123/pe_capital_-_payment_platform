-- DE! Permission for adf 

CREATE USER [your-adf-resource-name] FROM EXTERNAL PROVIDER;

ALTER ROLE db_ddladmin ADD MEMBER [your-adf-resource-name];
ALTER ROLE db_datawriter ADD MEMBER [your-adf-resource-name];
ALTER ROLE db_datareader ADD MEMBER [your-adf-resource-name];

--# permission for SQL ,Reader,Blob data reader
CREATE USER [your-email-address] FROM EXTERNAL PROVIDER;

ALTER ROLE db_ddladmin ADD MEMBER [your-email-address];
ALTER ROLE db_datawriter ADD MEMBER [your-email-address];
ALTER ROLE db_datareader ADD MEMBER [your-email-address];
