CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS companies (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sites (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL REFERENCES companies(id),
  name TEXT NOT NULL,
  address TEXT,
  timezone TEXT DEFAULT 'America/Los_Angeles',
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS employees (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL REFERENCES companies(id),
  full_name TEXT NOT NULL,
  phone_hash TEXT,
  email TEXT,
  role TEXT NOT NULL DEFAULT 'employee',
  status TEXT NOT NULL DEFAULT 'active',
  primary_site_id UUID REFERENCES sites(id),
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS employee_sites (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL REFERENCES companies(id),
  employee_id UUID NOT NULL REFERENCES employees(id),
  site_id UUID NOT NULL REFERENCES sites(id),
  permission_type TEXT DEFAULT 'allowed',
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shifts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL REFERENCES companies(id),
  site_id UUID NOT NULL REFERENCES sites(id),
  start_time TIMESTAMP NOT NULL,
  end_time TIMESTAMP NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shift_assignments (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL REFERENCES companies(id),
  shift_id UUID NOT NULL REFERENCES shifts(id),
  employee_id UUID NOT NULL REFERENCES employees(id),
  assignment_status TEXT NOT NULL DEFAULT 'assigned',
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS time_entries (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL REFERENCES companies(id),
  employee_id UUID NOT NULL REFERENCES employees(id),
  shift_id UUID REFERENCES shifts(id),
  clock_in TIMESTAMP NOT NULL,
  clock_out TIMESTAMP,
  total_minutes INTEGER,
  source TEXT DEFAULT 'system',
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS leave_requests (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL REFERENCES companies(id),
  employee_id UUID NOT NULL REFERENCES employees(id),
  shift_id UUID REFERENCES shifts(id),
  leave_type TEXT NOT NULL,
  reason TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shift_swap_requests (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL REFERENCES companies(id),
  requesting_employee_id UUID NOT NULL REFERENCES employees(id),
  target_employee_id UUID REFERENCES employees(id),
  shift_id UUID NOT NULL REFERENCES shifts(id),
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS call_audit_events (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL REFERENCES companies(id),
  call_id TEXT NOT NULL,
  employee_id UUID,
  intent TEXT NOT NULL,
  resource TEXT NOT NULL,
  operation TEXT NOT NULL,
  decision TEXT NOT NULL,
  reason TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS memory_documents (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL REFERENCES companies(id),
  source_type TEXT NOT NULL,
  source_id TEXT,
  visibility TEXT NOT NULL,
  employee_id UUID REFERENCES employees(id),
  site_id UUID REFERENCES sites(id),
  actian_chunk_id TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_employees_tenant_id ON employees(tenant_id);
CREATE INDEX IF NOT EXISTS idx_shifts_tenant_id ON shifts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_time_entries_employee ON time_entries(tenant_id, employee_id);
CREATE INDEX IF NOT EXISTS idx_leave_requests_employee ON leave_requests(tenant_id, employee_id);
CREATE INDEX IF NOT EXISTS idx_audit_call_id ON call_audit_events(call_id);
CREATE INDEX IF NOT EXISTS idx_memory_scope ON memory_documents(tenant_id, visibility, employee_id, site_id);
