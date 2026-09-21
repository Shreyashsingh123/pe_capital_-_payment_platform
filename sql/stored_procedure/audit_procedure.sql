CREATE PROCEDURE control.usp_AuditStart
    @run_id UNIQUEIDENTIFIER,
    @pipeline_name VARCHAR(200),
    @source_name VARCHAR(100) = NULL
AS
BEGIN
    INSERT INTO control.pipeline_audit (run_id, pipeline_name, source_name, start_time, status)
    VALUES (@run_id, @pipeline_name, @source_name, SYSUTCDATETIME(), 'RUNNING');
END


CREATE PROCEDURE control.usp_AuditComplete
    @run_id UNIQUEIDENTIFIER,
    @status VARCHAR(20),
    @records_read INT = NULL,
    @records_written INT = NULL,
    @error_message VARCHAR(MAX) = NULL
AS
BEGIN
    UPDATE control.pipeline_audit
    SET end_time = SYSUTCDATETIME(),
        status = @status,
        records_read = @records_read,
        records_written = @records_written,
        error_message = @error_message
    WHERE run_id = @run_id;
END
