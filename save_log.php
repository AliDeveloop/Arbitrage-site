<?php
// FILE 1: save_log.php
// این فایل را با نام save_log.php در هاست خود ذخیره کنید.

// یک کلید امنیتی ساده برای جلوگیری از دسترسی همگانی
// این کلید را با یک رشته تصادفی و پیچیده جایگزین کنید
$secret_key = "YOUR_SUPER_SECRET_KEY";

// بررسی می‌کنیم که درخواست از نوع POST باشد و کلید امنیتی درست باشد
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405); // Method Not Allowed
    die("Error: Only POST method is allowed.");
}

$auth_header = $_SERVER['HTTP_AUTHORIZATION'] ?? '';
if ($auth_header !== "Bearer " . $secret_key) {
    http_response_code(403); // Forbidden
    die("Error: Authentication failed.");
}

// دریافت داده‌های JSON از بدنه درخواست
$json_data = file_get_contents('php://input');
$prices = json_decode($json_data, true);

if (json_last_error() !== JSON_ERROR_NONE || !is_array($prices)) {
    http_response_code(400); // Bad Request
    die("Error: Invalid JSON data.");
}

// فرمت‌بندی و ذخیره داده‌ها
$log_file = 'price_log.txt';
$timestamp = date('Y-m-d H:i:s');
$log_entry = "--- Log at {$timestamp} ---\n";

foreach ($prices as $exchange => $price) {
    $price_str = $price ? $price : "N/A";
    $log_entry .= "Exchange: " . str_pad(ucfirst($exchange), 10) . " | Price: {$price_str}\n";
}
$log_entry .= "---\n\n";

// داده‌ها را به انتهای فایل اضافه می‌کنیم
file_put_contents($log_file, $log_entry, FILE_APPEND);

// پاسخ موفقیت‌آمیز
header('Content-Type: application/json');
echo json_encode(['status' => 'success', 'message' => 'Log saved.']);

?>


