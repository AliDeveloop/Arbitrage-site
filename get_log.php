<?php
// FILE 2: get_log.php
// این فایل را با نام get_log.php در هاست خود ذخیره کنید.

$log_file = 'price_log.txt';

if (file_exists($log_file)) {
    header('Content-Type: text/plain; charset=utf-8');
    readfile($log_file);
} else {
    // اگر فایل وجود نداشت، یک پاسخ خالی برمی‌گردانیم
    header('Content-Type: text/plain; charset=utf-8');
    echo "";
}
?>
```

**راهنما:**

* **فایل اول (`save_log.php`):** برای ذخیره کردن لاگ‌هاست.
* **فایل دوم (`get_log.php`):** برای خواندن و نمایش تمام لاگ‌های ذخیره شده است.

هر دو بخش کد را در فایل‌های جداگانه با نام‌های مشخص شده در هاست PHP خود قرار ده