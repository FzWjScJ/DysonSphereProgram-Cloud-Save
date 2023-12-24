package main

import (
    "fmt"
    "io"
    "io/ioutil"
    "log"
    "net/http"
    "os"
    "path/filepath"

    "github.com/google/uuid"
)

func createUserFolder() string {
    userUUID := uuid.New().String()
    folderPath := "./data/" + userUUID
    if err := os.MkdirAll(folderPath, os.ModePerm); err != nil {
        log.Fatalf("Error creating user folder: %v", err)
    }
    return userUUID
}

func initUUIDHandler(w http.ResponseWriter, r *http.Request) {
    if r.Method != http.MethodGet {
        http.Error(w, "Only GET method is allowed", http.StatusMethodNotAllowed)
        return
    }

    userUUID := createUserFolder()
    w.WriteHeader(http.StatusOK)
    w.Write([]byte(userUUID))
}

func downloadHandler(w http.ResponseWriter, r *http.Request) {
    userUUID := r.URL.Query().Get("uuid")
    if userUUID == "" {
        http.Error(w, "UUID is required", http.StatusBadRequest)
        return
    }

    folderPath := "./data/" + userUUID
    filePath := filepath.Join(folderPath, "archive.enc") // 假设文件名固定为 archive.enc

    if _, err := os.Stat(filePath); os.IsNotExist(err) {
        http.Error(w, "File not found", http.StatusNotFound)
        return
    }

    file, err := os.Open(filePath)
    if err != nil {
        http.Error(w, "Error opening file", http.StatusInternalServerError)
        return
    }
    defer file.Close()

    w.Header().Set("Content-Disposition", "attachment; filename=archive.enc")
    w.Header().Set("Content-Type", "application/octet-stream")

    _, err = io.Copy(w, file)
    if err != nil {
        log.Printf("Error writing file to response: %v", err)
    }
}

func uploadHandler(w http.ResponseWriter, r *http.Request) {
    if r.Method != http.MethodPost {
        http.Error(w, "Only POST method is allowed", http.StatusMethodNotAllowed)
        return
    }

    userUUID := r.URL.Query().Get("uuid")
    if userUUID == "" {
        http.Error(w, "UUID is required", http.StatusBadRequest)
        return
    }

    file, _, err := r.FormFile("file")
    if err != nil {
        http.Error(w, "Error retrieving the file", http.StatusBadRequest)
        return
    }
    defer file.Close()

    folderPath := "./data/" + userUUID
    filePath := filepath.Join(folderPath, "archive.enc") // Assuming a fixed file name for simplicity
    fileBytes, err := ioutil.ReadAll(file)
    if err != nil {
        http.Error(w, "Error reading file", http.StatusInternalServerError)
        return
    }

    err = ioutil.WriteFile(filePath, fileBytes, 0644)
    if err != nil {
        http.Error(w, "Error saving file", http.StatusInternalServerError)
        return
    }

    w.WriteHeader(http.StatusOK)
    w.Write([]byte("File uploaded successfully"))
}

func main() {
    if _, err := os.Stat("./log"); os.IsNotExist(err) {
        os.Mkdir("./log", os.ModePerm)
    }

    logFile, err := os.OpenFile("./log/server.log", os.O_RDWR|os.O_CREATE|os.O_APPEND, 0666)
    if err != nil {
        log.Fatalf("Error opening log file: %v", err)
    }
    defer logFile.Close()

    log.SetOutput(logFile)

    http.HandleFunc("/init-uuid", initUUIDHandler)
    http.HandleFunc("/upload", uploadHandler)
    http.HandleFunc("/download", downloadHandler)
    http.HandleFunc("/ping", func(w http.ResponseWriter, r *http.Request) {
        fmt.Fprintln(w, "PONG!!!")
    })

    log.Printf("Server started on :8080")
    log.Fatal(http.ListenAndServe(":8080", nil))
}

