import enum
from datetime import datetime, date, timedelta
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import (
    create_engine, Column, Integer, String, Date, DateTime, Boolean,
    Float, ForeignKey, Enum as SQLEnum, Text, or_
)
from sqlalchemy.orm import sessionmaker, relationship, declarative_base, Session
import bcrypt
import jwt

# =====================================================================
# 1. CẤU HÌNH CƠ SỞ DỮ LIỆU & BẢO MẬT
# =====================================================================
SQLALCHEMY_DATABASE_URL = "sqlite:///./sms_database.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

SECRET_KEY = "khoa_bi_mat_he_thong_quan_ly_sinh_vien_2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =====================================================================
# 2. ĐỊNH NGHĨA CÁC BẢNG CƠ SỞ DỮ LIỆU (MODELS - THEO SRS)
# =====================================================================
class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    STAFF = "STAFF"
    LECTURER = "LECTURER"
    STUDENT = "STUDENT"

class StudentStatus(str, enum.Enum):
    STUDYING = "STUDYING"
    RESERVED = "RESERVED"
    DROPPED = "DROPPED"

class AppealStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Announcement(Base):
    __tablename__ = "announcements"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    is_published = Column(Boolean, default=False)
    author_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

class Student(Base):
    __tablename__ = "students"
    student_code = Column(String(20), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    full_name = Column(String(100), nullable=False)
    dob = Column(Date, nullable=False)
    gender = Column(String(10), nullable=False)
    class_name = Column(String(50), nullable=False)
    cohort = Column(String(20), nullable=False)
    major = Column(String(100), nullable=True)
    phone = Column(String(15), nullable=False)
    status = Column(SQLEnum(StudentStatus), default=StudentStatus.STUDYING)

    enrollments = relationship("Enrollment", back_populates="student")

class Lecturer(Base):
    __tablename__ = "lecturers"
    lecturer_code = Column(String(20), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    full_name = Column(String(100), nullable=False)
    department = Column(String(100), nullable=True)
    phone = Column(String(15), nullable=True)

    classes = relationship("CourseClass", back_populates="lecturer")

class Course(Base):
    __tablename__ = "courses"
    course_code = Column(String(20), primary_key=True, index=True)
    course_name = Column(String(150), nullable=False)
    credits = Column(Integer, nullable=False)

class CourseClass(Base):
    __tablename__ = "course_classes"
    id = Column(Integer, primary_key=True, index=True)
    course_code = Column(String(20), ForeignKey("courses.course_code"), nullable=False)
    lecturer_code = Column(String(20), ForeignKey("lecturers.lecturer_code"), nullable=True)
    semester = Column(String(20), nullable=False)
    max_students = Column(Integer, default=50)
    room = Column(String(50), nullable=False)
    day_of_week = Column(Integer, nullable=False)
    start_period = Column(Integer, nullable=False)
    end_period = Column(Integer, nullable=False)
    is_grade_locked = Column(Boolean, default=False)
    is_closed = Column(Boolean, default=False)

    lecturer = relationship("Lecturer", back_populates="classes")
    enrollments = relationship("Enrollment", back_populates="course_class")

class Enrollment(Base):
    __tablename__ = "enrollments"
    id = Column(Integer, primary_key=True, index=True)
    student_code = Column(String(20), ForeignKey("students.student_code"), nullable=False)
    course_class_id = Column(Integer, ForeignKey("course_classes.id"), nullable=False)
    process_score = Column(Float, nullable=True)
    exam_score = Column(Float, nullable=True)
    final_score = Column(Float, nullable=True)

    student = relationship("Student", back_populates="enrollments")
    course_class = relationship("CourseClass", back_populates="enrollments")

class GradeAppeal(Base):
    __tablename__ = "grade_appeals"
    id = Column(Integer, primary_key=True, index=True)
    enrollment_id = Column(Integer, ForeignKey("enrollments.id"), nullable=False)
    reason = Column(Text, nullable=False)
    old_score = Column(Float, nullable=False)
    new_score = Column(Float, nullable=True)
    status = Column(SQLEnum(AppealStatus), default=AppealStatus.PENDING)
    handled_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# =====================================================================
# 3. HÀM BẢO MẬT & PHÂN QUYỀN 2 PHÂN HỆ
# =====================================================================
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if user is None:
        raise credentials_exception
    return user

def require_student(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Chỉ Sinh viên mới có quyền truy cập.")
    return current_user

def require_lecturer(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.LECTURER:
        raise HTTPException(status_code=403, detail="Chỉ Giảng viên mới có quyền truy cập.")
    return current_user

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Chỉ Quản trị viên (Admin) mới có quyền truy cập.")
    return current_user

def require_staff_or_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in [UserRole.STAFF, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Chỉ Cán bộ quản lý (Staff) hoặc Admin mới có quyền truy cập.")
    return current_user

# =====================================================================
# 4. SCHEMAS KIỂM TRA DỮ LIỆU ĐẦU VÀO (VALIDATION - SRS 1.5)
# =====================================================================
class ChangePasswordInput(BaseModel):
    old_password: str
    new_password: str

class ForgotPasswordInput(BaseModel):
    username: str
    email: EmailStr
    new_password: str

class AnnouncementInput(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    content: str = Field(..., min_length=5)
    is_published: bool = True

class StudentCreateInput(BaseModel):
    student_code: str = Field(..., min_length=3, max_length=20)
    username: str
    password: str
    email: EmailStr
    full_name: str
    dob: date
    gender: str
    class_name: str
    cohort: str
    major: Optional[str] = None
    phone: str = Field(..., pattern=r"^[0-9]{9,15}$")
    status: StudentStatus = StudentStatus.STUDYING

class StudentUpdateInput(BaseModel):
    full_name: str
    dob: date
    gender: str
    class_name: str
    cohort: str
    major: Optional[str] = None
    phone: str = Field(..., pattern=r"^[0-9]{9,15}$")
    status: StudentStatus

class GradeUpdateInput(BaseModel):
    student_code: str
    process_score: float = Field(..., ge=0, le=10)
    exam_score: float = Field(..., ge=0, le=10)

class AppealCreateInput(BaseModel):
    enrollment_id: int
    reason: str

class AppealResolveInput(BaseModel):
    status: AppealStatus
    new_score: Optional[float] = Field(None, ge=0, le=10)

class CourseCreateInput(BaseModel):
    course_code: str
    course_name: str
    credits: int = Field(..., ge=1, le=10)

class CourseClassCreateInput(BaseModel):
    course_code: str
    semester: str
    max_students: int = Field(50, ge=1)
    room: str
    day_of_week: int = Field(..., ge=2, le=8)
    start_period: int = Field(..., ge=1, le=12)
    end_period: int = Field(..., ge=1, le=12)

class AssignLecturerInput(BaseModel):
    course_class_id: int
    lecturer_code: str

class AssignStudentInput(BaseModel):
    course_class_id: int
    student_code: str

# =====================================================================
# 5. KHỞI TẠO ỨNG DỤNG & TẠO DỮ LIỆU MẪU BAN ĐẦU
# =====================================================================
app = FastAPI(title="Hệ thống Quản lý Sinh viên (SMS) - Toàn bộ hệ thống")

@app.on_event("startup")
def seed_initial_data():
    db = SessionLocal()
    if not db.query(User).first():
        admin_u = User(username="admin", password_hash=get_password_hash("123456"), email="admin@school.edu.vn", role=UserRole.ADMIN)
        staff_u = User(username="staff", password_hash=get_password_hash("123456"), email="staff@school.edu.vn", role=UserRole.STAFF)
        lec_u = User(username="giangvien1", password_hash=get_password_hash("123456"), email="gv1@school.edu.vn", role=UserRole.LECTURER)
        stu_u = User(username="sv001", password_hash=get_password_hash("123456"), email="sv001@school.edu.vn", role=UserRole.STUDENT)
        db.add_all([admin_u, staff_u, lec_u, stu_u])
        db.commit()

        db.add(Lecturer(lecturer_code="GV001", user_id=lec_u.id, full_name="TS. Nguyễn Văn A", department="CNTT", phone="0901234567"))
        db.add(Student(student_code="SV001", user_id=stu_u.id, full_name="Trần Thị B", dob=date(2005, 5, 15), gender="Nữ", class_name="K19-CNTT1", cohort="K19", major="Kỹ thuật phần mềm", phone="0987654321"))
        db.add(Announcement(title="Thông báo mở cổng đăng ký học phần kỳ 2026-1", content="Sinh viên theo dõi lịch học trên cổng thông tin.", is_published=True, author_id=admin_u.id))
        db.commit()
    db.close()

# =====================================================================
# 6. API DÙNG CHUNG: XÁC THỰC & QUẢN LÝ MẬT KHẨU (SRS 1.2)
# =====================================================================
@app.post("/api/auth/login", tags=["0. Dùng chung - Xác thực (SRS 1.2)"])
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Sai tên đăng nhập hoặc mật khẩu.")
    token = create_access_token(data={"sub": user.username, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "role": user.role}

@app.put("/api/auth/change-password", tags=["0. Dùng chung - Xác thực (SRS 1.2)"])
def change_password(payload: ChangePasswordInput, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Mật khẩu cũ không chính xác.")
    current_user.password_hash = get_password_hash(payload.new_password)
    db.commit()
    return {"message": "Đổi mật khẩu thành công."}

@app.post("/api/auth/forgot-password", tags=["0. Dùng chung - Xác thực (SRS 1.2)"])
def forgot_password(payload: ForgotPasswordInput, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username, User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Thông tin tài khoản và email không khớp.")
    user.password_hash = get_password_hash(payload.new_password)
    db.commit()
    return {"message": "Đặt lại mật khẩu thành công."}

# =====================================================================
# 7. PHÂN HỆ 1: CỔNG ĐÀO TẠO (GUEST, SINH VIÊN, GIẢNG VIÊN)
# =====================================================================
@app.get("/api/portal/public/announcements", tags=["Phân hệ 1 - Khách (SRS 1.1)"])
def get_public_announcements(db: Session = Depends(get_db)):
    return db.query(Announcement).filter(Announcement.is_published == True).order_by(Announcement.id.desc()).all()

@app.get("/api/portal/student/timetable", tags=["Phân hệ 1 - Sinh viên (SRS 1.3)"])
def view_personal_timetable(semester: str = "2026-1", current_user: User = Depends(require_student), db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    results = (
        db.query(CourseClass, Course)
        .join(Enrollment, Enrollment.course_class_id == CourseClass.id)
        .join(Course, Course.course_code == CourseClass.course_code)
        .filter(Enrollment.student_code == student.student_code, CourseClass.semester == semester)
        .all()
    )
    return [
        {
            "course_code": c.course_code, "course_name": c.course_name, "credits": c.credits,
            "room": cc.room, "day_of_week": cc.day_of_week, "periods": f"Tiết {cc.start_period}-{cc.end_period}"
        }
        for cc, c in results
    ]

@app.get("/api/portal/student/grades", tags=["Phân hệ 1 - Sinh viên (SRS 1.3)"])
def view_personal_grades(current_user: User = Depends(require_student), db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    records = (
        db.query(Enrollment, CourseClass, Course)
        .join(CourseClass, Enrollment.course_class_id == CourseClass.id)
        .join(Course, Course.course_code == CourseClass.course_code)
        .filter(Enrollment.student_code == student.student_code)
        .all()
    )
    return [
        {
            "enrollment_id": enr.id, "semester": cc.semester, "course_code": c.course_code,
            "course_name": c.course_name, "process_score": enr.process_score,
            "exam_score": enr.exam_score, "final_score": enr.final_score, "is_locked": cc.is_grade_locked
        }
        for enr, cc, c in records
    ]

@app.post("/api/portal/student/grade-appeals", tags=["Phân hệ 1 - Sinh viên (SRS 1.3)"])
def submit_grade_appeal(payload: AppealCreateInput, current_user: User = Depends(require_student), db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    enr = db.query(Enrollment).filter(Enrollment.id == payload.enrollment_id, Enrollment.student_code == student.student_code).first()
    if not enr or enr.final_score is None:
        raise HTTPException(status_code=400, detail="Học phần chưa có điểm để phúc khảo.")
    db.add(GradeAppeal(enrollment_id=enr.id, reason=payload.reason, old_score=enr.final_score))
    db.commit()
    return {"message": "Đã gửi yêu cầu phúc khảo thành công."}

@app.get("/api/portal/lecturer/teaching-timetable", tags=["Phân hệ 1 - Giảng viên (SRS 1.3)"])
def view_teaching_timetable(semester: str = "2026-1", current_user: User = Depends(require_lecturer), db: Session = Depends(get_db)):
    lec = db.query(Lecturer).filter(Lecturer.user_id == current_user.id).first()
    classes = db.query(CourseClass, Course).join(Course).filter(CourseClass.lecturer_code == lec.lecturer_code, CourseClass.semester == semester).all()
    return [
        {
            "class_id": cc.id, "course_code": c.course_code, "course_name": c.course_name,
            "room": cc.room, "day_of_week": cc.day_of_week, "periods": f"Tiết {cc.start_period}-{cc.end_period}",
            "is_grade_locked": cc.is_grade_locked
        }
        for cc, c in classes
    ]

@app.put("/api/portal/lecturer/classes/{class_id}/grades", tags=["Phân hệ 1 - Giảng viên (SRS 1.3)"])
def update_student_grades(class_id: int, payload: GradeUpdateInput, current_user: User = Depends(require_lecturer), db: Session = Depends(get_db)):
    lec = db.query(Lecturer).filter(Lecturer.user_id == current_user.id).first()
    cc = db.query(CourseClass).filter(CourseClass.id == class_id, CourseClass.lecturer_code == lec.lecturer_code).first()
    if not cc:
        raise HTTPException(status_code=403, detail="Bạn không phụ trách lớp học phần này.")
    if cc.is_grade_locked:
        raise HTTPException(status_code=400, detail="Lớp học phần đã bị khóa điểm.")
    enr = db.query(Enrollment).filter(Enrollment.course_class_id == class_id, Enrollment.student_code == payload.student_code).first()
    if not enr:
        raise HTTPException(status_code=404, detail="Sinh viên không thuộc lớp học phần này.")
    enr.process_score = payload.process_score
    enr.exam_score = payload.exam_score
    enr.final_score = round(payload.process_score * 0.4 + payload.exam_score * 0.6, 2)
    db.commit()
    return {"message": "Cập nhật điểm thành công.", "final_score": enr.final_score}

# =====================================================================
# 8. PHÂN HỆ 2: QUẢN TRỊ NỘI BỘ (ADMIN & STAFF)
# =====================================================================

# --- Mục 1.1: Quản lý thông báo công khai (Admin / Staff) ---
@app.post("/api/admin/announcements", tags=["Phân hệ 2 - Thông báo (SRS 1.1)"])
def create_announcement(payload: AnnouncementInput, current_user: User = Depends(require_staff_or_admin), db: Session = Depends(get_db)):
    data = payload.model_dump()
    data["is_published"] = True
    ann = Announcement(**data, author_id=current_user.id)
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return ann

@app.put("/api/admin/announcements/{ann_id}", tags=["Phân hệ 2 - Thông báo (SRS 1.1)"])
def update_announcement(ann_id: int, payload: AnnouncementInput, current_user: User = Depends(require_staff_or_admin), db: Session = Depends(get_db)):
    ann = db.query(Announcement).filter(Announcement.id == ann_id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông báo.")
    ann.title = payload.title
    ann.content = payload.content
    ann.is_published = payload.is_published
    db.commit()
    return ann

@app.delete("/api/admin/announcements/{ann_id}", tags=["Phân hệ 2 - Thông báo (SRS 1.1)"])
def delete_announcement(ann_id: int, current_user: User = Depends(require_staff_or_admin), db: Session = Depends(get_db)):
    ann = db.query(Announcement).filter(Announcement.id == ann_id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông báo.")
    db.delete(ann)
    db.commit()
    return {"message": "Đã gỡ bỏ thông báo."}

# --- Mục 1.4, 1.5, 1.6: Quản lý Hồ sơ Sinh viên (Staff / Admin) ---
@app.get("/api/admin/students", tags=["Phân hệ 2 - Sinh viên (SRS 1.4 - 1.6)"])
def view_and_search_students(
    search: Optional[str] = Query(None, description="Tìm theo mã SV hoặc họ tên"),
    sort_by: str = Query("student_code", regex="^(student_code|full_name|dob)$"),
    order: str = Query("asc", regex="^(asc|desc)$"),
    current_user: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db)
):
    query = db.query(Student)
    if search:
        query = query.filter(or_(Student.student_code.ilike(f"%{search}%"), Student.full_name.ilike(f"%{search}%")))
    sort_col = getattr(Student, sort_by)
    query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())
    return query.all()

@app.get("/api/admin/students/{student_code}", tags=["Phân hệ 2 - Sinh viên (SRS 1.4 - 1.6)"])
def view_student_detail(student_code: str, current_user: User = Depends(require_staff_or_admin), db: Session = Depends(get_db)):
    stu = db.query(Student).filter(Student.student_code == student_code).first()
    if not stu:
        raise HTTPException(status_code=404, detail="Không tìm thấy sinh viên.")
    return stu

@app.post("/api/admin/students", tags=["Phân hệ 2 - Sinh viên (SRS 1.4 - 1.6)"])
def add_student(payload: StudentCreateInput, current_user: User = Depends(require_staff_or_admin), db: Session = Depends(get_db)):
    if db.query(Student).filter(Student.student_code == payload.student_code).first():
        raise HTTPException(status_code=400, detail="Mã sinh viên đã tồn tại.")
    if db.query(User).filter(or_(User.username == payload.username, User.email == payload.email)).first():
        raise HTTPException(status_code=400, detail="Tên đăng nhập hoặc email đã được sử dụng.")

    new_user = User(username=payload.username, password_hash=get_password_hash(payload.password), email=payload.email, role=UserRole.STUDENT)
    db.add(new_user)
    db.flush()

    new_stu = Student(
        student_code=payload.student_code, user_id=new_user.id, full_name=payload.full_name,
        dob=payload.dob, gender=payload.gender, class_name=payload.class_name,
        cohort=payload.cohort, major=payload.major, phone=payload.phone, status=payload.status
    )
    db.add(new_stu)
    db.commit()
    return {"message": "Thêm hồ sơ sinh viên thành công.", "student_code": new_stu.student_code}

@app.put("/api/admin/students/{student_code}", tags=["Phân hệ 2 - Sinh viên (SRS 1.4 - 1.6)"])
def edit_student(student_code: str, payload: StudentUpdateInput, current_user: User = Depends(require_staff_or_admin), db: Session = Depends(get_db)):
    stu = db.query(Student).filter(Student.student_code == student_code).first()
    if not stu:
        raise HTTPException(status_code=404, detail="Không tìm thấy sinh viên.")
    for key, value in payload.model_dump().items():
        setattr(stu, key, value)
    db.commit()
    return {"message": "Cập nhật hồ sơ sinh viên thành công."}

@app.delete("/api/admin/students/{student_code}", tags=["Phân hệ 2 - Sinh viên (SRS 1.4 - 1.6)"])
def delete_student(student_code: str, current_user: User = Depends(require_staff_or_admin), db: Session = Depends(get_db)):
    stu = db.query(Student).filter(Student.student_code == student_code).first()
    if not stu:
        raise HTTPException(status_code=404, detail="Không tìm thấy sinh viên.")
    related_enrollments = db.query(Enrollment).filter(Enrollment.student_code == student_code).count()
    if related_enrollments > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Không thể xóa! Sinh viên đang có {related_enrollments} dữ liệu học phần/điểm số liên kết cần bảo toàn."
        )
    user = db.query(User).filter(User.id == stu.user_id).first()
    db.delete(stu)
    if user:
        db.delete(user)
    db.commit()
    return {"message": "Đã xóa hồ sơ sinh viên."}

# --- Mục 1.6: Khóa điểm & Quản lý phúc khảo (Staff / Admin) ---
@app.put("/api/admin/grades/classes/{class_id}/lock", tags=["Phân hệ 2 - Điểm & Phúc khảo (SRS 1.6)"])
def lock_class_grades(class_id: int, is_locked: bool = True, current_user: User = Depends(require_staff_or_admin), db: Session = Depends(get_db)):
    cc = db.query(CourseClass).filter(CourseClass.id == class_id).first()
    if not cc:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học phần.")
    cc.is_grade_locked = is_locked
    db.commit()
    return {"message": f"Đã {'khóa' if is_locked else 'mở khóa'} nhập điểm cho lớp học phần."}

@app.get("/api/admin/grades/appeals", tags=["Phân hệ 2 - Điểm & Phúc khảo (SRS 1.6)"])
def list_grade_appeals(current_user: User = Depends(require_staff_or_admin), db: Session = Depends(get_db)):
    return db.query(GradeAppeal).all()

@app.put("/api/admin/grades/appeals/{appeal_id}", tags=["Phân hệ 2 - Điểm & Phúc khảo (SRS 1.6)"])
def resolve_grade_appeal(appeal_id: int, payload: AppealResolveInput, current_user: User = Depends(require_staff_or_admin), db: Session = Depends(get_db)):
    appeal = db.query(GradeAppeal).filter(GradeAppeal.id == appeal_id).first()
    if not appeal:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu phúc khảo.")
    appeal.status = payload.status
    appeal.handled_by = current_user.id
    if payload.status == AppealStatus.APPROVED and payload.new_score is not None:
        appeal.new_score = payload.new_score
        enr = db.query(Enrollment).filter(Enrollment.id == appeal.enrollment_id).first()
        if enr:
            enr.final_score = payload.new_score
    db.commit()
    return {"message": "Đã xử lý yêu cầu phúc khảo."}

# --- Mục 1.7: Quản lý Học phần, Phân công & Kiểm tra trùng lịch (Admin / Staff) ---
def is_time_overlap(start1: int, end1: int, start2: int, end2: int) -> bool:
    return max(start1, start2) <= min(end1, end2)

@app.get("/api/admin/courses", tags=["Phân hệ 2 - Học phần & Lịch học (SRS 1.7)"])
def list_courses(current_user: User = Depends(require_staff_or_admin), db: Session = Depends(get_db)):
    return db.query(Course).all()

@app.get("/api/admin/courses/classes", tags=["Phân hệ 2 - Học phần & Lịch học (SRS 1.7)"])
def list_course_classes(current_user: User = Depends(require_staff_or_admin), db: Session = Depends(get_db)):
    return db.query(CourseClass).all()

@app.post("/api/admin/courses", tags=["Phân hệ 2 - Học phần & Lịch học (SRS 1.7)"])
def create_course(payload: CourseCreateInput, current_user: User = Depends(require_staff_or_admin), db: Session = Depends(get_db)):
    if db.query(Course).filter(Course.course_code == payload.course_code).first():
        raise HTTPException(status_code=400, detail="Mã môn học đã tồn tại.")
    course = Course(**payload.model_dump())
    db.add(course)
    db.commit()
    return course

@app.post("/api/admin/courses/classes", tags=["Phân hệ 2 - Học phần & Lịch học (SRS 1.7)"])
def create_course_class(payload: CourseClassCreateInput, current_user: User = Depends(require_staff_or_admin), db: Session = Depends(get_db)):
    if not db.query(Course).filter(Course.course_code == payload.course_code).first():
        raise HTTPException(status_code=404, detail="Mã môn học không tồn tại.")
    if payload.start_period > payload.end_period:
        raise HTTPException(status_code=400, detail="Tiết bắt đầu phải nhỏ hơn hoặc bằng tiết kết thúc.")

    same_room_classes = db.query(CourseClass).filter(
        CourseClass.semester == payload.semester,
        CourseClass.room == payload.room,
        CourseClass.day_of_week == payload.day_of_week,
        CourseClass.is_closed == False
    ).all()
    for c in same_room_classes:
        if is_time_overlap(payload.start_period, payload.end_period, c.start_period, c.end_period):
            raise HTTPException(status_code=400, detail=f"Trùng lịch phòng {payload.room} với lớp học phần ID {c.id}.")

    cc = CourseClass(**payload.model_dump())
    db.add(cc)
    db.commit()
    db.refresh(cc)
    return cc

@app.post("/api/admin/courses/assign-lecturer", tags=["Phân hệ 2 - Học phần & Lịch học (SRS 1.7)"])
def assign_teaching_schedule(payload: AssignLecturerInput, current_user: User = Depends(require_staff_or_admin), db: Session = Depends(get_db)):
    cc = db.query(CourseClass).filter(CourseClass.id == payload.course_class_id).first()
    lec = db.query(Lecturer).filter(Lecturer.lecturer_code == payload.lecturer_code).first()
    if not cc or not lec:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học phần hoặc giảng viên.")

    lec_classes = db.query(CourseClass).filter(
        CourseClass.lecturer_code == payload.lecturer_code,
        CourseClass.semester == cc.semester,
        CourseClass.day_of_week == cc.day_of_week,
        CourseClass.id != cc.id
    ).all()
    for other in lec_classes:
        if is_time_overlap(cc.start_period, cc.end_period, other.start_period, other.end_period):
            raise HTTPException(status_code=400, detail=f"Giảng viên bị trùng lịch dạy với lớp ID {other.id}.")

    cc.lecturer_code = payload.lecturer_code
    db.commit()
    return {"message": f"Đã phân công giảng viên {lec.full_name} phụ trách lớp {cc.id}."}

@app.post("/api/admin/courses/assign-student", tags=["Phân hệ 2 - Học phần & Lịch học (SRS 1.7)"])
def assign_course_to_student(payload: AssignStudentInput, current_user: User = Depends(require_staff_or_admin), db: Session = Depends(get_db)):
    cc = db.query(CourseClass).filter(CourseClass.id == payload.course_class_id).first()
    stu = db.query(Student).filter(Student.student_code == payload.student_code).first()
    if not cc or not stu:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học phần hoặc sinh viên.")

    current_enrolls = db.query(Enrollment).filter(Enrollment.course_class_id == cc.id).all()
    if any(e.student_code == stu.student_code for e in current_enrolls):
        raise HTTPException(status_code=400, detail="Sinh viên đã có trong lớp học phần này.")
    if len(current_enrolls) >= cc.max_students:
        raise HTTPException(status_code=400, detail="Lớp học phần đã đủ sĩ số tối đa.")

    student_classes = (
        db.query(CourseClass)
        .join(Enrollment, Enrollment.course_class_id == CourseClass.id)
        .filter(
            Enrollment.student_code == stu.student_code,
            CourseClass.semester == cc.semester,
            CourseClass.day_of_week == cc.day_of_week
        )
        .all()
    )
    for other in student_classes:
        if is_time_overlap(cc.start_period, cc.end_period, other.start_period, other.end_period):
            raise HTTPException(status_code=400, detail=f"Sinh viên bị trùng lịch học với lớp ID {other.id}.")

    db.add(Enrollment(student_code=stu.student_code, course_class_id=cc.id))
    db.commit()
    return {"message": f"Đã xếp sinh viên {stu.full_name} vào lớp {cc.id}."}