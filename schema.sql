CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE employees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scalekit_user_id TEXT UNIQUE,
    full_name TEXT NOT NULL,
    phone TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('employee', 'manager', 'admin')),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE sites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    address TEXT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE employee_site_access (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID REFERENCES employees(id) ON DELETE CASCADE,
    site_id UUID REFERENCES sites(id) ON DELETE CASCADE,
    can_work BOOLEAN DEFAULT true,
    UNIQUE(employee_id, site_id)
);

CREATE TABLE shifts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID REFERENCES employees(id),
    site_id UUID REFERENCES sites(id),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    status TEXT DEFAULT 'scheduled'
        CHECK (status IN ('scheduled', 'completed', 'missed', 'cancelled')),
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE leave_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID REFERENCES employees(id),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    reason TEXT,
    status TEXT DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'emergency')),
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE time_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID REFERENCES employees(id),
    shift_id UUID REFERENCES shifts(id),
    clock_in TIMESTAMP,
    clock_out TIMESTAMP,
    total_hours NUMERIC(5,2),
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_employee_id UUID REFERENCES employees(id),
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id UUID,
    decision TEXT CHECK (decision IN ('allowed', 'blocked')),
    reason TEXT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_shifts_employee_time ON shifts(employee_id, start_time, end_time);
CREATE INDEX idx_leave_employee_time ON leave_requests(employee_id, start_time, end_time);
CREATE INDEX idx_audit_actor ON audit_logs(actor_employee_id);