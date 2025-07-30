package main

import (
    "fmt"
    "log"
    "net/http"
)

func main() {
    http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
        fmt.Fprintf(w, "Hello from skeleton-key!")
    })
    
    http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("Content-Type", "application/json")
        fmt.Fprintf(w, `{"status": "ok", "service": "skeleton-key"}`)
    })
    
    port := ":8080"
    fmt.Printf("🚀 Server starting on http://localhost%s\n", port)
    log.Fatal(http.ListenAndServe(port, nil))
}
