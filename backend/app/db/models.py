import uuid

from app.db.database import Base
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func


class Employee(Base):
    __tablename__ = "employees"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scalekit_user_id = Column(Text, unique=True)
    full_name = Column(Text, nullable=False)
    phone = Column(Text, unique=True, nullable=False)
    email = Column(Text, unique=True)
    role = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class Site(Base):
    __tablename__ = "sites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    address = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class EmployeeSiteAccess(Base):
    __tablename__ = "employee_site_access"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(
        UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE")
    )
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"))
    can_work = Column(Boolean, default=True)


class Shift(Base):
    __tablename__ = "shifts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"))
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id"))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(Text, default="scheduled")
    created_at = Column(DateTime, server_default=func.now())


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    reason = Column(Text)
    status = Column(Text, default="pending")
    created_at = Column(DateTime, server_default=func.now())


class TimeEntry(Base):
    __tablename__ = "time_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"))
    shift_id = Column(UUID(as_uuid=True), ForeignKey("shifts.id"))
    clock_in = Column(DateTime)
    clock_out = Column(DateTime)
    total_hours = Column(Numeric(5, 2))
    created_at = Column(DateTime, server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"))
    action = Column(Text, nullable=False)
    resource_type = Column(Text, nullable=False)
    resource_id = Column(UUID(as_uuid=True))
    decision = Column(Text)
    reason = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
