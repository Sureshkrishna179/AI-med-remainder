-- Database Schema for AI Medicine Reminder

-- Users Table (Caregivers)
CREATE TABLE IF NOT EXISTS users (
    user_id    INT AUTO_INCREMENT PRIMARY KEY,
    username   VARCHAR(50)  NOT NULL UNIQUE,
    password   VARCHAR(255) NOT NULL,
    role       VARCHAR(20)  DEFAULT 'Caregiver'
);

-- Medication Schedules
CREATE TABLE IF NOT EXISTS schedules (
    schedule_id   INT AUTO_INCREMENT PRIMARY KEY,
    patient_name  VARCHAR(100) NOT NULL,
    medicine_name VARCHAR(100) NOT NULL,
    dosage        VARCHAR(50)  NOT NULL,
    alarm_time    TIME         NOT NULL,
    is_active     BOOLEAN      DEFAULT TRUE,
    created_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

-- Patient Adherence Logs
CREATE TABLE IF NOT EXISTS adherence_logs (
    log_id       INT AUTO_INCREMENT PRIMARY KEY,
    schedule_id  INT          NOT NULL,
    triggered_at DATETIME     NOT NULL,
    status       VARCHAR(20)  NOT NULL,
    FOREIGN KEY (schedule_id) REFERENCES schedules(schedule_id)
        ON DELETE CASCADE
);
