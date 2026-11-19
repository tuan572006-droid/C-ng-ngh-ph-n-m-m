import streamlit as st
import requests

API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="EduManager - Hệ thống Quản lý Sinh viên", page_icon="🎓", layout="wide")

# Tùy chỉnh màu sắc giao diện phong cách EduManager (Sidebar xanh navy, nền sáng)
st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background-color: #0b2e59;
    }
    [data-testid="stSidebar"] * {
        color: #ffffff !important;
    }
    [data-testid="stSidebar"] .stButton > button {
        background-color: rgba(255, 255, 255, 0.14);
        border: 1px solid rgba(255, 255, 255, 0.25);
        color: white !important;
        width: 100%;
    }
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 16px;
        border-radius: 14px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
</style>
""", unsafe_allow_html=True)

if "token" not in st.session_state:
    st.session_state.token = None
    st.session_state.user = None

def api_get(endpoint):
    headers = {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}
    return requests.get(f"{API_URL}{endpoint}", headers=headers)

def api_post(endpoint, json_data=None, form_data=None):
    headers = {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}
    if form_data:
        return requests.post(f"{API_URL}{endpoint}", data=form_data)
    return requests.post(f"{API_URL}{endpoint}", json=json_data, headers=headers)

def api_put(endpoint, json_data=None):
    headers = {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}
    return requests.put(f"{API_URL}{endpoint}", json=json_data, headers=headers)

# ==========================================
# 1. MÀN HÌNH ĐĂNG NHẬP & THÔNG BÁO CÔNG KHAI
# ==========================================
if not st.session_state.get("token") or not st.session_state.get("user"):
    col1, col2 = st.columns([1.1, 1], gap="large")
    
    with col1:
        st.title("🎓 EduManager")
        st.caption("NATIONAL UNIVERSITY • HỆ THỐNG QUẢN LÝ SINH VIÊN")
        st.subheader("📢 Thông báo chung")
        try:
            res = api_get("/api/portal/public/announcements")
            if res.status_code == 200 and res.json():
                for ann in res.json():
                    with st.container(border=True):
                        st.markdown(f"**{ann['title']}**")
                        st.write(ann["content"])
            else:
                st.info("Chưa có thông báo công khai nào.")
        except Exception:
            st.error("⚠️ Chưa kết nối được Backend! Hãy chắc chắn bạn đang chạy `python -m uvicorn main:app --reload` ở một Terminal khác.")

    with col2:
        with st.container(border=True):
            st.subheader("🔐 Đăng nhập hệ thống")
            with st.form("login_form"):
                username = st.text_input("Tên đăng nhập", placeholder="Ví dụ: sv001, giangvien1, admin")
                password = st.text_input("Mật khẩu", type="password", value="123456")
                submitted = st.form_submit_button("Đăng nhập", use_container_width=True, type="primary")
                if submitted:
                    res = api_post("/api/auth/login", form_data={"username": username, "password": password})
                    if res.status_code == 200:
                        data = res.json()
                        st.session_state.token = data["access_token"]
                        st.session_state.user = {"username": username, "role": data["role"]}
                        st.rerun()
                    else:
                        st.error("Sai tên đăng nhập hoặc mật khẩu!")
            st.caption("Tài khoản mẫu (Mật khẩu chung: `123456`): `sv001` (Sinh viên) | `giangvien1` (Giảng viên) | `admin` (Quản trị)")

# ==========================================
# 2. GIAO DIỆN CHÍNH SAU KHI ĐĂNG NHẬP
# ==========================================
else:
    user = st.session_state.user
    role = user["role"]

    with st.sidebar:
        st.markdown("## 🎓 EduManager")
        st.caption("NATIONAL UNIVERSITY")
        st.divider()
        st.write(f"👤 **{user['username'].upper()}**")
        st.caption(f"Vai trò: {role}")
        st.divider()

        if role == "STUDENT":
            menu = st.radio("WORKSPACE", ["🏠 Tổng quan (Overview)", "📅 Thời khóa biểu", "📊 Kết quả học tập", "📝 Phúc khảo điểm", "👤 Hồ sơ cá nhân"])
        elif role == "LECTURER":
            menu = st.radio("WORKSPACE", ["🏠 Tổng quan (Overview)", "📅 Lịch giảng dạy", "✍️ Nhập điểm sinh viên"])
        else:
            menu = st.radio("WORKSPACE", ["🏠 Bảng điều khiển", "🎓 Quản lý Sinh viên", "📚 Quản lý Học phần", "⚖️ Duyệt phúc khảo"])

        st.divider()
        if st.button("↪ Đăng xuất"):
            st.session_state.token = None
            st.session_state.user = None
            st.rerun()

    # ------------------------------------------
    # PHÂN HỆ 1: SINH VIÊN
    # ------------------------------------------
    if role == "STUDENT":
        st.caption("STUDENT PORTAL")
        tt_res = api_get("/api/portal/student/timetable")
        gr_res = api_get("/api/portal/student/grades")
        timetable = tt_res.json() if tt_res.status_code == 200 else []
        grades = gr_res.json() if gr_res.status_code == 200 else []

        if menu == "🏠 Tổng quan (Overview)":
            st.title(f"Chào buổi sáng, {user['username'].upper()}! 👋")
            st.write("Chúc bạn một ngày học tập hiệu quả và tràn đầy năng lượng.")

            valid_scores = [g["final_score"] for g in grades if g.get("final_score") is not None]
            avg10 = round(sum(valid_scores) / len(valid_scores), 2) if valid_scores else 0.0
            gpa4 = round((avg10 / 10) * 4, 2)
            total_credits = sum(g.get("credits", 0) for g in grades)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("📘 Môn học hiện tại", f"{len(timetable)} môn", f"{total_credits} tín chỉ")
            c2.metric("📈 GPA Hệ 4", f"{gpa4}", "Tích lũy")
            c3.metric("🎓 Điểm TB Hệ 10", f"{avg10}", "Thang điểm 10")
            c4.metric("🗓️ Lớp trong tuần", f"{len(timetable)} lớp", "Học kỳ 1")

            st.divider()
            left, right = st.columns([1.6, 1], gap="large")
            with left:
                st.subheader("📅 Lịch học các lớp học phần")
                if timetable:
                    for c in timetable:
                        with st.container(border=True):
                            st.markdown(f"**{c['course_name']}** (`{c['course_code']}`)")
                            st.caption(f"📚 Số tín chỉ: {c.get('credits', '')}  |  📍 Phòng: {c.get('room') or 'Chưa xếp'}  |  ⏰ Thứ {c.get('day_of_week')} ({c.get('periods') or 'Chưa xếp lịch'})")
                else:
                    st.info("Bạn chưa được xếp vào lớp học phần nào.")

            with right:
                st.subheader("🔔 Thông báo mới")
                anns = api_get("/api/portal/public/announcements").json()
                for a in anns:
                    with st.container(border=True):
                        st.markdown(f"**{a['title']}**")
                        st.caption(a["content"])

        elif menu == "📅 Thời khóa biểu":
            st.title("📅 Thời khóa biểu cá nhân")
            st.dataframe(timetable, use_container_width=True)

        elif menu == "📊 Kết quả học tập":
            st.title("📊 Bảng điểm tổng hợp")
            st.dataframe(grades, use_container_width=True)

        elif menu == "📝 Phúc khảo điểm":
            st.title("📝 Gửi đơn phúc khảo điểm")
            if not grades:
                st.warning("Bạn chưa có học phần nào để phúc khảo.")
            else:
                options = {f"{g['course_name']} ({g['course_code']}) - Điểm: {g.get('final_score', 'N/A')}": g["enrollment_id"] for g in grades}
                selected = st.selectbox("Chọn học phần cần phúc khảo", list(options.keys()))
                reason = st.text_area("Lý do phúc khảo")
                if st.button("Gửi đơn phúc khảo", type="primary"):
                    r = api_post("/api/portal/student/grade-appeals", {"enrollment_id": options[selected], "reason": reason})
                    if r.status_code == 200:
                        st.success("Đã gửi đơn phúc khảo thành công!")
                    else:
                        st.error("Không thể gửi đơn.")

        elif menu == "👤 Hồ sơ cá nhân":
            st.title("👤 Hồ sơ sinh viên")
            prof = api_get("/api/portal/student/profile").json()
            st.json(prof)

    # ------------------------------------------
    # PHÂN HỆ 1: GIẢNG VIÊN
    # ------------------------------------------
    elif role == "LECTURER":
        st.caption("LECTURER PORTAL")
        res = api_get("/api/portal/lecturer/schedule")
        classes = res.json() if res.status_code == 200 else []

        if menu in ["🏠 Tổng quan (Overview)", "📅 Lịch giảng dạy"]:
            st.title(f"Chào buổi sáng, Giảng viên {user['username'].upper()}! 👋")
            c1, c2, c3 = st.columns(3)
            c1.metric("📚 Lớp được phân công", f"{len(classes)} lớp")
            c2.metric("👥 Tổng sinh viên phụ trách", f"{sum(c.get('enrolled_count', 0) for c in classes)} SV")
            c3.metric("✍️ Trạng thái nhập điểm", "Đang mở")

            st.subheader("Danh sách lớp học phần giảng dạy")
            if classes:
                for c in classes:
                    with st.container(border=True):
                        st.markdown(f"**{c['course_name']}** (`{c['class_code']}`)")
                        st.caption(f"👥 Sĩ số: {c['enrolled_count']} SV  |  📍 Phòng: {c.get('room') or 'Chưa xếp'}  |  ⏰ Lịch: {c.get('schedule') or 'Chưa xếp'}")
            else:
                st.info("Chưa có lớp học phần nào được phân công.")

        elif menu == "✍️ Nhập điểm sinh viên":
            st.title("✍️ Nhập điểm sinh viên theo lớp")
            if not classes:
                st.info("Bạn chưa phụ trách lớp học phần nào.")
            else:
                class_map = {f"{c['course_name']} ({c['class_code']})": c["class_id"] for c in classes}
                selected_cls = st.selectbox("Chọn lớp học phần", list(class_map.keys()))
                cid = class_map[selected_cls]
                st_list = api_get(f"/api/portal/lecturer/classes/{cid}/students").json()

                if not st_list:
                    st.warning("Lớp này chưa có sinh viên đăng ký.")
                else:
                    for sv in st_list:
                        with st.container(border=True):
                            col_a, col_b, col_c, col_d = st.columns([2, 1, 1, 1])
                            col_a.write(f"**{sv['student_code']}** - {sv['full_name']}")
                            qt = col_b.number_input("Điểm QT", 0.0, 10.0, float(sv["process_score"] or 0.0), key=f"qt_{sv['enrollment_id']}")
                            thi = col_c.number_input("Điểm Thi", 0.0, 10.0, float(sv["exam_score"] or 0.0), key=f"thi_{sv['enrollment_id']}")
                            if col_d.button("Lưu điểm", key=f"btn_{sv['enrollment_id']}"):
                                r = api_put(f"/api/portal/lecturer/classes/{cid}/grades", [{"enrollment_id": sv["enrollment_id"], "process_score": qt, "exam_score": thi}])
                                if r.status_code == 200:
                                    st.success(f"Đã lưu điểm cho {sv['student_code']}!")

    # ------------------------------------------
    # PHÂN HỆ 2: ADMIN / STAFF (ĐẦY ĐỦ FORM THÊM MỚI & XẾP LỊCH)
    # ------------------------------------------
    else:
        st.caption("ADMIN & STAFF MANAGEMENT PORTAL")
        
        # 0. BẢNG ĐIỀU KHIỂN & ĐĂNG THÔNG BÁO
        if menu == "🏠 Bảng điều khiển":
            st.title("🏠 Bảng điều khiển & Quản lý Thông báo")
            
            res_sv = api_get("/api/admin/students")
            list_sv = res_sv.json() if res_sv.status_code == 200 and isinstance(res_sv.json(), list) else []
            res_c = api_get("/api/admin/courses")
            list_c = res_c.json() if res_c.status_code == 200 and isinstance(res_c.json(), list) else []
            res_ap = api_get("/api/admin/grade-appeals")
            list_ap = res_ap.json() if res_ap.status_code == 200 and isinstance(res_ap.json(), list) else []

            col1, col2, col3 = st.columns(3)
            col1.metric("🎓 Tổng số Sinh viên", len(list_sv))
            col2.metric("📚 Tổng số Học phần", len(list_c))
            col3.metric("⚖️ Đơn phúc khảo", len(list_ap))

            st.divider()
            st.subheader("📢 Đăng thông báo mới lên Trang Đăng nhập")
            with st.form("announcement_form"):
                tb_title = st.text_input("Tiêu đề thông báo *", placeholder="VD: Thông báo lịch đăng ký học phần")
                tb_content = st.text_area("Nội dung chi tiết *", placeholder="Nhập nội dung gửi tới sinh viên...")
                if st.form_submit_button("Đăng thông báo", type="primary"):
                    if not tb_title.strip() or not tb_content.strip():
                        st.warning("Vui lòng nhập đầy đủ tiêu đề và nội dung!")
                    else:
                        r = api_post("/api/admin/announcements", json_data={
                            "title": tb_title,
                            "content": tb_content
                        })
                        if r.status_code in [200, 201]:
                            st.success("Đã đăng thông báo lên trang đăng nhập!")
                            st.rerun()
                        else:
                            st.error("Không thể đăng thông báo.")

            st.subheader("📋 Các thông báo đã đăng")
            res_tb = api_get("/api/portal/public/announcements")
            ds_tb = res_tb.json() if res_tb.status_code == 200 and isinstance(res_tb.json(), list) else []
            for tb in ds_tb:
                with st.container(border=True):
                    st.markdown(f"**{tb['title']}** — *{tb['created_at']}*")
                    st.write(tb["content"])

        # 1. QUẢN LÝ HỒ SƠ SINH VIÊN
        elif menu == "🎓 Quản lý Sinh viên":
            st.title("🎓 Quản lý Hồ sơ Sinh viên")
            with st.expander("➕ Thêm hồ sơ sinh viên mới", expanded=True):
                with st.form("add_student_form"):
                    c1, c2, c3 = st.columns(3)
                    s_code = c1.text_input("Mã sinh viên *", placeholder="VD: SV002")
                    s_name = c2.text_input("Họ và tên *", placeholder="VD: Nguyễn Văn B")
                    s_gender = c3.selectbox("Giới tính *", ["Nam", "Nữ"])
                    
                    c4, c5, c6 = st.columns(3)
                    s_dob = c4.date_input("Ngày sinh")
                    s_class = c5.text_input("Lớp hành chính *", placeholder="VD: K19-CNTT1")
                    s_cohort = c6.text_input("Khóa *", value="K19")

                    c7, c8, c9 = st.columns(3)
                    s_major = c7.text_input("Chuyên ngành", value="Công nghệ thông tin")
                    s_email = c8.text_input("Email *", placeholder="sv002@school.edu.vn")
                    s_phone = c9.text_input("Số điện thoại *", placeholder="0901234567")
                    
                    if st.form_submit_button("Lưu hồ sơ sinh viên", type="primary"):
                        payload = {
                            "student_code": s_code.strip().upper(),
                            "username": s_code.strip().lower(),
                            "password": "123456",
                            "email": s_email.strip(),
                            "full_name": s_name.strip(),
                            "dob": str(s_dob),
                            "gender": s_gender,
                            "class_name": s_class.strip(),
                            "cohort": s_cohort.strip(),
                            "major": s_major.strip(),
                            "phone": s_phone.strip()
                        }
                        res = api_post("/api/admin/students", json_data=payload)
                        if res.status_code in [200, 201]:
                            st.success(f"Đã thêm sinh viên {s_name} ({s_code.upper()})! Tài khoản đăng nhập: {s_code.lower()} / 123456")
                            st.rerun()
                        else:
                            st.error(f"Lỗi: {res.json().get('detail', 'Không thể thêm sinh viên')}")

            st.subheader("Danh sách Sinh viên hiện có")
            students = api_get("/api/admin/students").json()
            st.dataframe(students, use_container_width=True)

        # 2. QUẢN LÝ HỌC PHẦN, LỚP HỌC & XẾP LỊCH
        elif menu == "📚 Quản lý Học phần":
            st.title("📚 Quản lý Học phần, Lớp học & Lịch học")
            tab1, tab2, tab3 = st.tabs(["1️⃣ Tạo Môn học (Course)", "2️⃣ Mở Lớp & Xếp Lịch học", "3️⃣ Xếp Sinh viên vào Lớp"])

            # TAB 1: TẠO MÔN HỌC
            with tab1:
                with st.form("add_course_form"):
                    c1, c2, c3 = st.columns([1, 2, 1])
                    c_code = c1.text_input("Mã học phần *", placeholder="VD: IT3080")
                    c_name = c2.text_input("Tên học phần *", placeholder="VD: Mạng máy tính")
                    c_cred = c3.number_input("Số tín chỉ", min_value=1, max_value=10, value=3)
                    if st.form_submit_button("Tạo học phần", type="primary"):
                        r = api_post("/api/admin/courses", json_data={
                            "course_code": c_code,
                            "course_name": c_name,
                            "credits": int(c_cred)
                        })
                        if r.status_code in [200, 201]:
                            st.success(f"Đã tạo học phần {c_name}!")
                            st.rerun()
                        else:
                            st.error(f"Lỗi: {r.json().get('detail', 'Không thể tạo học phần')}")
                
                res_c = api_get("/api/admin/courses")
                courses = res_c.json() if res_c.status_code == 200 and isinstance(res_c.json(), list) else []
                st.dataframe(courses, use_container_width=True)

            # TAB 2: MỞ LỚP HỌC PHẦN, PHÂN CÔNG GIẢNG VIÊN & LỊCH HỌC
            # TAB 2: MỞ LỚP HỌC PHẦN, PHÂN CÔNG GIẢNG VIÊN & LỊCH HỌC
            with tab2:
                res_c = api_get("/api/admin/courses")
                courses = res_c.json() if res_c.status_code == 200 and isinstance(res_c.json(), list) else []
                if not courses:
                    st.warning("Hãy tạo ít nhất 1 học phần ở Tab 1 trước.")
                else:
                    with st.form("add_class_form"):
                        course_opts = {f"{c['course_code']} - {c['course_name']}": c["course_code"] for c in courses}
                        sel_course = st.selectbox("Chọn học phần *", list(course_opts.keys()))
                        
                        c1, c2, c3 = st.columns(3)
                        sem = c1.text_input("Học kỳ *", value="2026-1")
                        room = c2.text_input("Phòng học *", placeholder="VD: D3-401")
                        lec_code = c3.text_input("Mã Giảng viên phụ trách", value="GV001")
                        
                        c4, c5, c6 = st.columns(3)
                        dow = c4.selectbox("Thứ trong tuần *", [2, 3, 4, 5, 6, 7], format_func=lambda x: f"Thứ {x}")
                        s_per = c5.number_input("Tiết bắt đầu *", min_value=1, max_value=12, value=1)
                        e_per = c6.number_input("Tiết kết thúc *", min_value=1, max_value=12, value=3)
                        
                        if st.form_submit_button("Mở lớp & Lưu lịch học", type="primary"):
                            r = api_post("/api/admin/courses/classes", json_data={
                                "course_code": course_opts[sel_course],
                                "semester": sem,
                                "max_students": 50,
                                "room": room,
                                "day_of_week": int(dow),
                                "start_period": int(s_per),
                                "end_period": int(e_per)
                            })
                            if r.status_code in [200, 201]:
                                new_cls_id = r.json().get("id")
                                if lec_code and new_cls_id:
                                    api_post("/api/admin/courses/assign-lecturer", json_data={
                                        "course_class_id": new_cls_id,
                                        "lecturer_code": lec_code
                                    })
                                st.success(f"Đã mở lớp ID {new_cls_id} (Thứ {dow}, Tiết {s_per}-{e_per}, Phòng {room})!")
                                st.rerun()
                            else:
                                st.error(f"Lỗi: {r.json().get('detail', 'Không thể mở lớp')}")

                st.subheader("Danh sách lớp học phần đã mở")
                res_cls = api_get("/api/admin/courses/classes")
                cls_list = res_cls.json() if res_cls.status_code == 200 and isinstance(res_cls.json(), list) else []
                st.dataframe(cls_list, use_container_width=True)

            # TAB 3: XẾP SINH VIÊN VÀO LỚP ĐỂ HIỆN LỊCH HỌC
            with tab3:
                with st.form("assign_student_form"):
                    c1, c2 = st.columns(2)
                    target_class_id = c1.number_input("ID Lớp học phần (xem ở Tab 2)", min_value=1, step=1, value=1)
                    target_sv_code = c2.text_input("Mã Sinh viên *", value="SV001", placeholder="VD: SV001")
                    if st.form_submit_button("Xếp sinh viên vào lớp", type="primary"):
                        r = api_post("/api/admin/courses/assign-student", json_data={
                            "course_class_id": int(target_class_id),
                            "student_code": target_sv_code.strip().upper()
                        })
                        if r.status_code in [200, 201]:
                            st.success(f"Đã xếp sinh viên {target_sv_code.upper()} vào lớp ID {target_class_id}!")
                        else:
                            st.error(f"Lỗi: {r.json().get('detail', 'Không thể xếp lớp')}")

        # 3. DUYỆT PHÚC KHẢO
        elif menu == "⚖️ Duyệt phúc khảo":
            st.title("⚖️ Danh sách Đơn phúc khảo điểm")
            appeals = api_get("/api/admin/grade-appeals").json()
            st.dataframe(appeals, use_container_width=True)