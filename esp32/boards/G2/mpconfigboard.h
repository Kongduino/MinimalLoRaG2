#define MICROPY_HW_BOARD_NAME       "Meshtastic Mesh Device Station G2"
#define MICROPY_HW_MCU_NAME         "ESP32S3"
#define MICROPY_PY_MACHINE_DAC      (0)
// Enable UART REPL for modules that have an external USB-UART and don't use native USB.
#define MICROPY_HW_ENABLE_UART_REPL (1)
#define MICROPY_HW_I2C0_SCL         (6)
#define MICROPY_HW_I2C0_SDA         (5)
#define MICROPY_HW_SPI1_MOSI        (13)
#define MICROPY_HW_SPI1_MISO        (14)
#define MICROPY_HW_SPI1_SCK         (12)
#define MICROPY_HW_SPI1_CS          (11)
