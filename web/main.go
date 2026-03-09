package main

import (
	"encoding/json"
	"net/http"
	"os"
	"strings"
	"sync"

	"github.com/gin-gonic/gin"
)

type Notice struct {
	Title     string `json:"title"`
	Time      string `json:"time"`
	Link      string `json:"link"`
	Important bool   `json:"important"`
}

type StockData struct {
	Name    string   `json:"name"`
	Notices []Notice `json:"notices"`
}

var mutex sync.Mutex

func getFilePath(filename string) string {
	path := "/app/data/" + filename
	if _, err := os.Stat(path); os.IsNotExist(err) {
		return "../data/" + filename // fallback for local testing
	}
	return path
}

func main() {
	r := gin.Default()

	// Load HTML templates
	r.LoadHTMLGlob("templates/*")

	// Route for the web page
	r.GET("/", func(c *gin.Context) {
		c.HTML(http.StatusOK, "index.html", gin.H{
			"title": "A股公告监控",
		})
	})

	r.GET("/chart", func(c *gin.Context) {
		c.HTML(http.StatusOK, "chart.html", gin.H{
			"title": "A股公告与走势分析",
		})
	})

	r.GET("/api/history", func(c *gin.Context) {
		file, err := os.ReadFile(getFilePath("stock_history.json"))
		if err != nil {
			c.JSON(http.StatusOK, gin.H{})
			return
		}
		c.Data(http.StatusOK, "application/json", file)
	})

	// API to fetch the latest notices
	r.GET("/api/notices", func(c *gin.Context) {
		file, err := os.ReadFile(getFilePath("latest_notices.json"))
		if err != nil {
			c.JSON(http.StatusOK, gin.H{}) // Return empty if not yet fetched
			return
		}

		var data map[string]StockData
		if err := json.Unmarshal(file, &data); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to parse data"})
			return
		}

		c.JSON(http.StatusOK, data)
	})

	// API to get currently monitored stocks
	r.GET("/api/stocks", func(c *gin.Context) {
		file, err := os.ReadFile(getFilePath("stocks.json"))
		if err != nil {
			c.JSON(http.StatusOK, gin.H{})
			return
		}
		var stocks map[string]string
		if err := json.Unmarshal(file, &stocks); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to parse stocks"})
			return
		}
		c.JSON(http.StatusOK, stocks)
	})

	// API to add a new stock to monitor
	r.POST("/api/stocks", func(c *gin.Context) {
		var req struct {
			Query string `json:"query"`
		}
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request"})
			return
		}

		query := strings.TrimSpace(req.Query)
		if query == "" {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Query cannot be empty"})
			return
		}

		// Read mapping
		mappingFile, err := os.ReadFile(getFilePath("stock_mapping.json"))
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Stock mapping not ready, please try again later"})
			return
		}

		var mapping map[string]string
		if err := json.Unmarshal(mappingFile, &mapping); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to parse mapping"})
			return
		}

		var targetCode, targetName string
		// Check if query is code
		if name, ok := mapping[query]; ok {
			targetCode = query
			targetName = name
		} else {
			// Check if query is name
			for code, name := range mapping {
				if name == query {
					targetCode = code
					targetName = name
					break
				}
			}
		}

		if targetCode == "" {
			c.JSON(http.StatusNotFound, gin.H{"error": "Stock not found"})
			return
		}

		mutex.Lock()
		defer mutex.Unlock()

		stocksPath := getFilePath("stocks.json")
		stocksFile, _ := os.ReadFile(stocksPath)
		var stocks map[string]string
		if len(stocksFile) > 0 {
			json.Unmarshal(stocksFile, &stocks)
		} else {
			stocks = make(map[string]string)
		}

		stocks[targetCode] = targetName

		newData, _ := json.MarshalIndent(stocks, "", "  ")
		os.WriteFile(stocksPath, newData, 0644)
		
		// 稍微改变一下文件的修改时间（如果有需要的话），让 Python 服务更快感知
		// 在这里不用显式写，os.WriteFile 已经更新了修改时间

		c.JSON(http.StatusOK, gin.H{"code": targetCode, "name": targetName})
	})

	// API to delete a monitored stock
	r.DELETE("/api/stocks/:code", func(c *gin.Context) {
		code := c.Param("code")

		mutex.Lock()
		defer mutex.Unlock()

		stocksPath := getFilePath("stocks.json")
		stocksFile, _ := os.ReadFile(stocksPath)
		var stocks map[string]string
		if len(stocksFile) > 0 {
			if err := json.Unmarshal(stocksFile, &stocks); err == nil {
				delete(stocks, code)
				newData, _ := json.MarshalIndent(stocks, "", "  ")
				os.WriteFile(stocksPath, newData, 0644)
			}
		}

		// 同时清理 latest_notices.json 里的缓存，让网页立马不显示它
		latestPath := getFilePath("latest_notices.json")
		latestFile, _ := os.ReadFile(latestPath)
		var latestData map[string]StockData
		if len(latestFile) > 0 {
			if err := json.Unmarshal(latestFile, &latestData); err == nil {
				delete(latestData, code)
				newData, _ := json.MarshalIndent(latestData, "", "  ")
				os.WriteFile(latestPath, newData, 0644)
			}
		}

		c.JSON(http.StatusOK, gin.H{"status": "deleted"})
	})

	// Run the server on port 8083
	r.Run(":8083")
}
