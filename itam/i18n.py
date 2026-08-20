from flask import g

AR = {
    "Dashboard": "لوحة التحكم",
    "Assets": "الأصول",
    "Checkouts": "الإعارات",
    "Lending": "الإعارة",
    "Licenses": "التراخيص",
    "Maintenance": "الصيانة",
    "Inventory": "الجرد",
    "Locations": "المواقع",
    "Employees": "الموظفون",
    "Departments": "الأقسام",
    "Vendors": "الموردون",
    "Procurement": "المشتريات",
    "QR Scanner": "ماسح QR",
    "Reports": "التقارير",
    "Analytics": "التحليلات",
    "Users": "المستخدمون",
    "Activity": "سجل النشاط",
    "Settings": "الإعدادات",
    "Notifications": "الإشعارات",
    "Search": "بحث",
    "Log in": "تسجيل الدخول",
    "Log out": "تسجيل الخروج",
    "Profile": "الملف الشخصي",
    "Total Assets": "إجمالي الأصول",
    "Checked Out": "معار",
    "Under Maintenance": "قيد الصيانة",
    "Expiring Warranties": "ضمانات على وشك الانتهاء",
    "Total Asset Value": "القيمة الإجمالية للأصول",
    "Active Licenses": "التراخيص الفعالة",
    "Available Assets": "الأصول المتاحة",
    "Retired / Disposed": "مستبعد / متخلص منه",
    "Assets by Category": "الأصول حسب الفئة",
    "Assets by Status": "الأصول حسب الحالة",
    "Recent Activity": "النشاط الأخير",
    "Quick Actions": "إجراءات سريعة",
    "Add Asset": "إضافة أصل",
    "New Asset": "أصل جديد",
    "Check Out": "إعارة",
    "Check In": "إرجاع",
    "Available": "متاح",
    "Reserved": "محجوز",
    "Retired": "مستبعد",
    "Missing": "مفقود",
    "In Use": "قيد الاستخدام",
    "In Storage": "في المخزن",
    "Lost": "مفقود",
    "Damaged": "تالف",
    "Disposed": "متخلص منه",
    "Name": "الاسم",
    "Status": "الحالة",
    "Category": "الفئة",
    "Location": "الموقع",
    "Department": "القسم",
    "Employee": "الموظف",
    "Save": "حفظ",
    "Cancel": "إلغاء",
    "Delete": "حذف",
    "Edit": "تعديل",
    "Actions": "إجراءات",
    "Overdue": "متأخر",
    "Backups": "النسخ الاحتياطية",
    "Roles": "الأدوار",
    "Print": "طباعة",
    "Export CSV": "تصدير CSV",
    "Import": "استيراد",
}


# ---------------------------------------------------------------------------
# Everything else the interface says. Most of these live in templates that
# never called t(), which is why the Arabic view was still largely English.
# translate_html() below applies them on the way out, so a string only has to
# be listed here once to appear translated everywhere it is used.
AR.update({
    # --- actions and buttons
    "Export": "تصدير", "Export Excel": "تصدير Excel", "Export Excel/CSV": "تصدير Excel/CSV",
    "Import Excel/CSV": "استيراد Excel/CSV", "Excel/CSV": "Excel/CSV",
    "Filter": "تصفية", "Clear": "مسح", "Apply": "تطبيق", "Save": "حفظ",
    "Save changes": "حفظ التغييرات", "Save settings": "حفظ الإعدادات",
    "Save permissions": "حفظ الصلاحيات", "Save search": "حفظ البحث",
    "Cancel": "إلغاء", "Delete": "حذف", "Edit": "تعديل", "Add": "إضافة",
    "Select all": "تحديد الكل", "Clear selection": "إلغاء التحديد",
    "Select row": "تحديد الصف", "Delete selected": "حذف المحدد",
    "Check in selected": "استلام المحدد", "Manage": "إدارة",
    "Next": "التالي", "Previous": "السابق", "Page": "صفحة", "of": "من",
    "Start": "بدء", "Complete": "إنهاء", "Upload": "رفع", "Download": "تنزيل",
    "Restore": "استعادة", "Revoke": "سحب", "Transfer": "نقل", "Reserve": "حجز",
    "Clone": "نسخ", "Info": "معلومات", "Contact": "اتصال", "Read": "مقروء",
    "Mark all read": "تعليم الكل كمقروء", "Start over": "البدء من جديد",
    "Run report": "تشغيل التقرير", "Open asset": "فتح الأصل",
    "Start camera": "تشغيل الكاميرا", "Set password": "تعيين كلمة المرور",
    "Change password": "تغيير كلمة المرور", "Create backup now": "إنشاء نسخة احتياطية الآن",
    "Start physical audit": "بدء جرد فعلي", "Complete audit": "إنهاء الجرد",
    "Assign seat": "تخصيص مقعد", "Assign a seat": "تخصيص مقعد",
    "Upload & preview": "رفع ومعاينة", "Import valid rows": "استيراد الصفوف الصالحة",

    # --- filters
    "All": "الكل", "All statuses": "كل الحالات", "All categories": "كل الفئات",
    "All departments": "كل الأقسام", "All branches": "كل الفروع",
    "All buildings": "كل المباني", "All floors": "كل الطوابق",
    "All locations": "كل المواقع", "All conditions": "كل الحالات الفنية",
    "All actions": "كل الإجراءات", "Any status": "أي حالة", "Any category": "أي فئة",
    "Any department": "أي قسم", "Any condition": "أي حالة فنية",

    # --- field labels
    "Name": "الاسم", "Name *": "الاسم *", "Tag": "الرمز", "Asset ID": "رقم الأصل",
    "Serial": "الرقم التسلسلي", "Serial number": "الرقم التسلسلي",
    "Manufacturer": "الشركة المصنعة", "Model": "الطراز", "Type": "النوع",
    "Category": "الفئة", "Categories": "الفئات", "Status": "الحالة",
    "Condition": "الحالة الفنية", "Branch": "الفرع", "Building": "المبنى",
    "Floor": "الطابق", "Room": "الغرفة", "Location": "الموقع",
    "Location name": "اسم الموقع", "Department": "القسم", "Department name": "اسم القسم",
    "Vendor": "المورد", "Purchase date": "تاريخ الشراء", "Purchase cost": "تكلفة الشراء",
    "Purchase value": "قيمة الشراء", "Warranty expiry": "انتهاء الضمان",
    "Invoice number": "رقم الفاتورة", "Depreciation (years)": "الإهلاك (سنوات)",
    "Operating system": "نظام التشغيل", "CPU": "المعالج", "RAM": "الذاكرة",
    "Storage": "التخزين", "Graphics card": "كرت الشاشة", "MAC address": "عنوان MAC",
    "IP address": "عنوان IP", "Hostname": "اسم الجهاز", "Notes": "ملاحظات",
    "Notes (optional)": "ملاحظات (اختياري)", "Email": "البريد الإلكتروني",
    "Phone": "الهاتف", "Title": "المسمى", "Job title": "المسمى الوظيفي",
    "Employee ID": "رقم الموظف", "Employee type": "نوع الموظف",
    "Active": "نشط", "Website": "الموقع الإلكتروني", "Cost": "التكلفة",
    "Cost center": "مركز التكلفة", "Seats": "المقاعد", "Seats *": "المقاعد *",
    "Used": "المستخدم", "Expiry": "الانتهاء", "Kind": "النوع", "Inside": "داخل",
    "Path": "المسار", "Count": "العدد", "Total": "الإجمالي", "Result": "النتيجة",
    "Due": "الاستحقاق", "Due date": "تاريخ الاستحقاق", "Returned": "أُعيد",
    "Checked out": "معار", "Assigned to": "مخصص إلى", "Assign to": "تخصيص إلى",
    "Edited by": "عُدّل بواسطة", "Updated by": "حُدّث بواسطة",
    "Technician": "الفني", "Scheduled": "مجدول", "Scheduled for": "مجدول في",
    "Started": "بدأ", "Completed": "اكتمل", "Verified": "تم التحقق",
    "Found": "موجود", "Since": "منذ", "When": "متى", "From": "من", "To": "إلى",
    "User": "المستخدم", "Username": "اسم المستخدم", "Role": "الدور",
    "Password": "كلمة المرور", "Action": "الإجراء", "Entity": "العنصر",
    "Last login": "آخر دخول", "API key": "مفتاح API", "File": "الملف",
    "Size": "الحجم", "Number": "الرقم", "Description": "الوصف", "Qty": "الكمية",
    "Permission": "الصلاحية", "Contact person": "الشخص المسؤول",
    "Last location": "آخر موقع", "Licence": "الترخيص", "License key": "مفتاح الترخيص",
    "Compliance": "الامتثال", "Compliant": "متوافق", "Perpetual": "دائم",
    "Assets held": "الأصول المستلمة", "Asset value": "قيمة الأصول",
    "Current value": "القيمة الحالية", "Details": "التفاصيل", "Labels": "الملصقات",
    "Label": "ملصق", "Equipment": "المعدات", "Missing": "مفقود",

    # --- headings
    "Assets": "الأصول", "Employees": "الموظفون", "Audits": "عمليات الجرد",
    "Missing assets": "الأصول المفقودة", "Equipment we own": "المعدات التي نملكها",
    "Software we own": "البرمجيات التي نملكها", "By status": "حسب الحالة",
    "Software licences": "تراخيص البرمجيات", "Audits run": "عمليات الجرد المنفذة",
    "Total purchase value": "إجمالي قيمة الشراء", "Assignment history": "سجل التخصيص",
    "Assignment History": "سجل التخصيص", "Transfer History": "سجل النقل",
    "Seat assignments": "تخصيص المقاعد", "Timeline": "التسلسل الزمني",
    "Attached components": "المكونات المرتبطة", "Account": "الحساب",
    "Stored backups": "النسخ الاحتياطية المحفوظة", "Camera scan": "المسح بالكاميرا",
    "Manual entry": "إدخال يدوي", "Asset categories": "فئات الأصول",
    "Custom report builder": "منشئ التقارير المخصصة",
    "Roles & permissions": "الأدوار والصلاحيات",
    "Technical specifications": "المواصفات الفنية",
    "Active reservations": "الحجوزات النشطة", "Ready for checkout": "جاهز للإعارة",
    "Assets by Department": "الأصول حسب القسم",
    "Assets due for return": "أصول مستحقة الإعادة",
    "Currently checked out": "المعار حالياً", "Assets checked out": "الأصول المعارة",
    "Lost or missing assets": "أصول مفقودة", "End of life assets": "أصول منتهية العمر",
    "Need repair or disposal": "تحتاج إصلاحاً أو تخلصاً",

    # --- empty states and messages
    "No assets found.": "لا توجد أصول.", "No assets found": "لا توجد أصول",
    "No data.": "لا توجد بيانات.", "No history.": "لا يوجد سجل.",
    "No checkouts.": "لا توجد إعارات.", "No employees yet.": "لا يوجد موظفون بعد.",
    "No departments yet.": "لا توجد أقسام بعد.", "No locations yet.": "لا توجد مواقع بعد.",
    "No categories yet.": "لا توجد فئات بعد.", "No licenses yet.": "لا توجد تراخيص بعد.",
    "No backups yet.": "لا توجد نسخ احتياطية بعد.",
    "No maintenance tasks.": "لا توجد مهام صيانة.",
    "No maintenance history.": "لا يوجد سجل صيانة.",
    "No notifications.": "لا توجد إشعارات.", "No files yet.": "لا توجد ملفات بعد.",
    "No seats assigned.": "لا توجد مقاعد مخصصة.",
    "No vendors/stores yet.": "لا يوجد موردون/متاجر بعد.",
    "No purchase orders.": "لا توجد أوامر شراء.",
    "No recorded events.": "لا توجد أحداث مسجلة.",
    "Never assigned.": "لم يُخصص مطلقاً.", "Nothing yet.": "لا شيء بعد.",
    "No activity recorded.": "لا يوجد نشاط مسجل.",
    "No assets from this vendor.": "لا توجد أصول من هذا المورد.",
    "No assets on record yet.": "لا توجد أصول مسجلة بعد.",
    "No software licences recorded yet.": "لا توجد تراخيص برمجيات مسجلة بعد.",
    "No assets selected.": "لم يتم تحديد أصول.",
    "No results": "لا توجد نتائج",
    "Nothing checked out.": "لا يوجد شيء معار.",
    "Nothing is currently checked out.": "لا يوجد شيء معار حالياً.",
    "Nothing due in the next 7 days.": "لا شيء مستحق خلال 7 أيام.",
    "No available assets to lend right now.": "لا توجد أصول متاحة للإعارة حالياً.",
    "No assets match these filters.": "لا توجد أصول تطابق هذه المرشحات.",
    "No employees available for checkout.": "لا يوجد موظفون متاحون للإعارة.",
    "No audits yet. Start one to verify your physical inventory.":
        "لا توجد عمليات جرد بعد. ابدأ واحدة للتحقق من الجرد الفعلي.",
    "No reservations. Reserve assets from the asset page.":
        "لا توجد حجوزات. احجز الأصول من صفحة الأصل.",

    # --- placeholders and hints
    "Search": "بحث", "Search locations": "بحث في المواقع",
    "Optional": "اختياري", "Other…": "أخرى…",
    "— (unassigned)": "— (غير مخصص)",
    "Room or storage area": "غرفة أو منطقة تخزين",
    "Type the room name": "اكتب اسم الغرفة",
    "Type the operating system": "اكتب نظام التشغيل",
    "Auto — pick a category": "تلقائي — اختر فئة",
    "Audit name (optional)": "اسم الجرد (اختياري)",
    "Asset tag or serial number": "رمز الأصل أو الرقم التسلسلي",
    "Name this search…": "سمِّ هذا البحث…",
    "Search by Asset ID, name or serial…": "ابحث برقم الأصل أو الاسم أو التسلسلي…",
    "Optional — plenty of staff don't have one.":
        "اختياري — كثير من الموظفين ليس لديهم بريد إلكتروني.",
    "Generated for you — change it if your school numbers staff differently.":
        "تم توليده تلقائياً — غيّره إذا كانت مدرستك ترقّم الموظفين بطريقة أخرى.",
    "Set automatically when the asset is saved.": "يُضبط تلقائياً عند حفظ الأصل.",
    "Everything the school owns — equipment and software — in one place.":
        "كل ما تملكه المدرسة — معدات وبرمجيات — في مكان واحد.",
    "Menu": "القائمة", "Update ready": "تحديث جاهز", "version": "الإصدار",
    "has been downloaded; your data is not affected.":
        "تم تنزيله؛ بياناتك غير متأثرة.",
    "An administrator can install it from Settings.":
        "يمكن للمسؤول تثبيته من الإعدادات.",
    "Update now": "التحديث الآن",
    "Change location": "تغيير الموقع",
    "Light theme": "الوضع الفاتح",
    "Dark theme": "الوضع الداكن",
    "Rotate printed label 90° (tick this if labels come out sideways)":
        "تدوير الملصق المطبوع 90 درجة (فعّل هذا إذا خرجت الملصقات جانبية)",
    "Held by classes & rooms": "بحوزة الصفوف والغرف",
    "Shared devices assigned to a class or room in the inventory sheet — not borrowed by a person.":
        "أجهزة مشتركة مخصصة لصف أو غرفة في ملف الجرد — ليست معارة لشخص.",
    "Release": "تحرير",
    "Delete all": "حذف الكل",
    "Delete ALL": "حذف كل",
    "assets and their history? This cannot be undone.":
        "أصلاً مع كامل سجلها؟ لا يمكن التراجع عن هذا.",
    "Set department": "تعيين القسم",
    "Set type": "تعيين النوع",
    "Set condition": "تعيين الحالة الفنية",
    "Mark active": "تفعيل",
    "Mark inactive": "إلغاء التفعيل",
    "Bulk action for selected:": "إجراء جماعي للمحدد:",
    "Reservation": "الحجز",
    "Notes (optional)": "ملاحظات (اختياري)",
    "Handheld scanner / manual entry": "ماسح يدوي / إدخال يدوي",
    "Plug in a USB barcode scanner (Datalogic, Zebra, …), leave the cursor in the box, and scan the label's barcode — the asset opens by itself. Typing the tag works the same way.":
        "وصّل ماسح باركود USB ‏(Datalogic، Zebra، …)، واترك المؤشر في الحقل، وامسح باركود الملصق — يُفتح الأصل تلقائياً. كتابة الرقم تعمل بالطريقة نفسها.",
    "Asset tag or serial number": "رقم الأصل أو الرقم التسلسلي",
    "Open asset": "فتح الأصل",
    "Update automatically (downloads new versions and installs them at a quiet moment)":
        "التحديث تلقائياً (ينزّل الإصدارات الجديدة ويثبتها في وقت هادئ)",
    "Software update": "تحديث البرنامج",
    "Current version": "الإصدار الحالي",
    "is ready to install": "جاهز للتثبيت",
    "Checks GitHub for a newer build, installs it, and restarts AMS by itself. The database, uploads and backups are never touched.":
        "يبحث عن إصدار أحدث على GitHub ويثبته ويعيد تشغيل AMS تلقائياً. قاعدة البيانات والمرفقات والنسخ الاحتياطية لا تُمسّ أبداً.",
    "Updating…": "جارٍ التحديث…",
    "AMS is updating": "AMS قيد التحديث",
    "The app restarts by itself with the new version — this takes under a minute, and your data is not affected.":
        "يعيد التطبيق تشغيل نفسه بالإصدار الجديد — يستغرق ذلك أقل من دقيقة، وبياناتك غير متأثرة.",
    "Waiting for AMS to come back…": "بانتظار عودة AMS…",
    "Taking longer than expected — start AMS.exe on the server, then reload this page.":
        "يستغرق وقتاً أطول من المتوقع — شغّل AMS.exe على الخادم ثم أعد تحميل هذه الصفحة.",

    # --- shell rail groups
    "Operations": "العمليات", "Registry": "السجل", "People": "الأشخاص",
    "Insight": "الرؤى",

    # --- landing page
    "Product": "المنتج", "Workflow": "سير العمل", "Sign in": "تسجيل الدخول",
    "Asset register": "سجل الأصول",
    "Every device on campus, accounted for.": "كل جهاز في الحرم المدرسي، محسوب.",
    "AMS is the IT department's register: what the school owns, where it lives, who holds it, and when it comes back. Lending, warranties, licenses, maintenance and inventory in one place — in English and Arabic.":
        "AMS هو سجل قسم تقنية المعلومات: ما تملكه المدرسة، وأين يوجد، ومن يحمله، ومتى يعود. الإعارة والضمانات والتراخيص والصيانة والجرد في مكان واحد — بالعربية والإنجليزية.",
    "Enter AMS": "دخول AMS",
    "Assets tracked": "أصل مسجّل", "On loan today": "معار اليوم",
    "Rooms & stores": "غرفة ومخزن", "Languages": "لغتان",
    "Built for the daily round": "مصمم للجولة اليومية",
    "Scan to find": "امسح لتجد",
    "Every asset carries a QR label. Scan it with any phone and the record opens.":
        "كل أصل يحمل ملصق QR. امسحه بأي هاتف ويفتح السجل.",
    "Lending in two clicks": "إعارة بنقرتين",
    "Check equipment out to a member of staff with a due date, and back in when it returns.":
        "أعر الأجهزة لموظف مع تاريخ استحقاق، واستلمها عند عودتها.",
    "Warranty watch": "مراقبة الضمان",
    "Expiring warranties and licenses surface on the dashboard before they lapse.":
        "تظهر الضمانات والتراخيص المنتهية على لوحة التحكم قبل انقضائها.",
    "Licenses beside hardware": "التراخيص بجانب الأجهزة",
    "Seats owned against seats in use, kept next to the machines they run on.":
        "المقاعد المملوكة مقابل المستخدمة، بجانب الأجهزة التي تعمل عليها.",
    "Term-end inventory": "جرد نهاية الفصل",
    "Physical audits record what was verified and what is missing, room by room.":
        "يسجل الجرد الفعلي ما تم التحقق منه وما هو مفقود، غرفة غرفة.",
    "Arabic and English": "العربية والإنجليزية",
    "The whole interface mirrors to Arabic, right to left, per user.":
        "الواجهة كاملة تنعكس إلى العربية، من اليمين إلى اليسار، لكل مستخدم.",
    "Ready to sign in?": "جاهز لتسجيل الدخول؟",
    "Use your school account. Access is limited to IT-department staff.":
        "استخدم حساب مدرستك. الوصول مقصور على موظفي قسم تقنية المعلومات.",
    "IT Department": "قسم تقنية المعلومات", "Internal system": "نظام داخلي",

    # --- sign-in
    "Back": "رجوع",
    "The register is behind the door.": "السجل خلف الباب.",
    "Every device on campus, its holder, its history. Sign in with your IT-department account to continue.":
        "كل جهاز في الحرم، حامله، وتاريخه. سجّل الدخول بحساب قسم تقنية المعلومات للمتابعة.",
    "Sign in to AMS": "تسجيل الدخول إلى AMS",
    "Use your school account.": "استخدم حساب مدرستك.",
    "Forgot password?": "نسيت كلمة المرور؟",
    "Access to this system is logged.": "الوصول إلى هذا النظام مسجّل.",
})

LANGS = {"en": "English", "ar": "العربية"}


def t(text):
    lang = getattr(g, "lang", "en")
    if lang == "ar":
        return AR.get(text, text)
    return text


# ---------------------------------------------------------------------------

import re as _re

#: Text nodes and these attributes are translated on the way out.
_TEXT = _re.compile(r">([^<>]+)<")
_ATTR = _re.compile(r'(placeholder|title|aria-label)="([^"<>]+)"')
_SKIP = _re.compile(r"<(script|style|textarea)\b.*?</\1>", _re.S | _re.I)


def translate_html(html):
    """Translate a rendered page into Arabic.

    Most of the interface is written straight into the templates rather than
    through t(), so the Arabic view was still largely English. Wrapping several
    hundred strings by hand across forty templates would be a large and
    error-prone change; translating the finished page needs one dictionary
    entry per phrase and nothing else.

    Only *exact* whole strings that appear in AR are replaced, so a value a
    user typed is left alone unless it happens to equal a phrase we translate,
    and script, style and textarea contents are skipped entirely.
    """
    if not html:
        return html

    holes = []

    def stash(match):
        holes.append(match.group(0))
        return f"\x00{len(holes) - 1}\x00"

    html = _SKIP.sub(stash, html)

    def swap_text(match):
        raw = match.group(1)
        word = raw.strip()
        hit = AR.get(word)
        if not hit:
            return match.group(0)
        lead = raw[:len(raw) - len(raw.lstrip())]
        tail = raw[len(raw.rstrip()):]
        return f">{lead}{hit}{tail}<"

    def swap_attr(match):
        hit = AR.get(match.group(2).strip())
        return f'{match.group(1)}="{hit}"' if hit else match.group(0)

    html = _TEXT.sub(swap_text, html)
    html = _ATTR.sub(swap_attr, html)
    return _re.sub(r"\x00(\d+)\x00", lambda m: holes[int(m.group(1))], html)
