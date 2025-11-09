package distro

import (
	"bufio"
	"fmt"
	"os"
	"runtime"
	"strings"
)

type OsType string

const (
	Linux OsType = "linux"
	MacOs OsType = "darwin"
)

type Distro string

const (
	Ubuntu      Distro = "ubuntu"
	PopOs       Distro = "popos"
	Debian      Distro = "debian"
	MacOsDistro Distro = "macos"
)

type PackageManager string

const (
	Apt      PackageManager = "apt"
	Homebrew PackageManager = "homebrew"
)

type Info struct {
	OS              OsType
	Distro          Distro
	Version         string
	CodeName        string
	PackageManagers []PackageManager
	Arch            string // e.g., amd64, arm64
}

func Detect() (*Info, error) {
	info := &Info{
		Arch: runtime.GOARCH,
	}

	osType := runtime.GOOS
	switch osType {
	case "linux":
		info.OS = Linux
		if err := detectLinuxDistro(info); err != nil {
			return nil, fmt.Errorf("failed to detect the distro")
		}

	case "darwin":
		info.OS = MacOs
		if err := detectMacOs(info); err != nil {
			return nil, fmt.Errorf("failed to detect the macOS version")
		}

	case "windows":
		return nil, fmt.Errorf("windows is not supported")

	default:
		return nil, fmt.Errorf("unsupported operating system: %s", osType)
	}

	detectPackageManagers(info)

	return info, nil
}

func detectLinuxDistro(info *Info) error {
	// try to read /etc/os-release
	if err := parseOsRelease(info); err == nil {
		return nil
	}

	if err := parseLsbRelease(info); err == nil {
		return nil
	}

	info.Distro = Distro("unknown")
	return fmt.Errorf("could not detect linux distribution")
}

func parseOsRelease(info *Info) error {
	file, err := os.Open("/etc/os-release")
	if err != nil {
		return err
	}

	defer file.Close()

	data := make(map[string]string)
	scanner := bufio.NewScanner(file)

	for scanner.Scan() {
		line := scanner.Text()
		parts := strings.SplitN(line, "=", 2)
		if len(parts) == 2 {
			key := strings.TrimSpace(parts[0])
			value := strings.Trim(strings.TrimSpace(parts[1]), "\"")
			data[key] = value
		}
	}

	if err := scanner.Err(); err != nil {
		return err
	}

	//distro info
	if id, ok := data["ID"]; ok {
		info.Distro = normalizeDistroName(id)
	}

	if version, ok := data["VERSION_ID"]; ok {
		info.Version = version
	}

	if codename, ok := data["VERSION_CODENAME"]; ok {
		info.CodeName = codename
	}

	return nil
}

func parseLsbRelease(info *Info) error {
	file, err := os.Open("/etc/lsb-release")
	if err != nil {
		return err
	}

	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "DISTRIB_ID=") {
			distroID := strings.TrimPrefix(line, "DISTRIB_ID")
			distroID = strings.Trim(distroID, "\"")
			info.Distro = normalizeDistroName(distroID)
		}
		if strings.HasPrefix(line, "DISTRIB_RELEASE=") {
			info.Version = strings.TrimPrefix(line, "DISTRIB_RELEASE=")
			info.Version = strings.Trim(info.Version, "\"")
		}

		if strings.HasPrefix(line, "DISTRIB_CODENAME=") {
			info.CodeName = strings.TrimPrefix(line, "DISTRIB_CODENAME=")
			info.CodeName = strings.Trim(info.CodeName, "\"")
		}
	}

	return scanner.Err()
}

func detectMacOs(info *Info) error {
	info.Distro = MacOsDistro

	data, err := os.ReadFile("/System/Library/CoreServices/SystemVersion.plist")
	if err != nil {
		return err
	}

	content := string(data)

	if idx := strings.Index(content, "<key>ProductVersion</key>"); idx != -1 {
		substr := content[idx:]
		if startIdx := strings.Index(substr, "<string>"); startIdx != -1 {
			substr = substr[startIdx+8:] // 8 is len("<string>")
			if endIdx := strings.Index(substr, "</string>"); endIdx != -1 {
				info.Version = substr[:endIdx]
			}
		}
	}

	info.CodeName = getMacOsCodeName(info.Version)

	return nil
}

func getMacOsCodeName(version string) string {
	parts := strings.Split(version, ".")
	if len(parts) == 0 {
		return ""
	}

	switch parts[0] {
	case "14":
		return "Sonoma"
	case "13":
		return "Sonoma"
	}
	return ""
}

func detectPackageManagers(info *Info) {
	managers := []PackageManager{}

	if info.OS == MacOs {
		if commandExists("brew") {
			managers = append(managers, Homebrew)
		}
		info.PackageManagers = managers
		return
	}

	switch info.Distro {
	case Ubuntu, PopOs, Debian:
		if commandExists("apt") {
			managers = append(managers, Apt)
		}
	}

	if commandExists("snap") {
		managers = append(managers, "snap")
	}

	if commandExists("flatpak") {
		managers = append(managers, "flatpak")
	}

	info.PackageManagers = managers
}

func normalizeDistroName(name string) Distro {
	name = strings.ToLower(name)

	switch {
	case strings.Contains(name, "ubuntu"):
		return Ubuntu
	case strings.Contains(name, "popos"), strings.Contains(name, "pop!_os"):
		return PopOs
	case strings.Contains(name, "debian"):
		return Debian
	default:
		return Distro("unknown")
	}
}

func commandExists(cmd string) bool {
	_, err := os.Stat("/usr/bin" + cmd)
	if err == nil {
		return true
	}

	_, err = os.Stat("/usr/local/bin" + cmd)
	if err == nil {
		return true
	}

	_, err = os.Stat("/opt/homebrew/bin/" + cmd)
	return err == nil
}

func (i *Info) String() string {
	managers := []string{}
	for _, pm := range i.PackageManagers {
		managers = append(managers, string(pm))
	}

	return fmt.Sprintf("OS: %s\nDistro: %s %s (%s)\nArch: %s\nPackage Managers: %s", i.OS, i.Distro, i.Version, i.CodeName, i.Arch, strings.Join(managers, ", "))
}


func(i *Info) IsLinux() bool {
	return i.OS == Linux
}


func (i *Info) IsMacOs() bool {
	return i.OS == MacOs
}


func (i *Info) HasPackageManager(pm PackageManager) bool {
	for _, manager := range i.PackageManagers {
		if manager == pm {
			return true
		}
	}
	return false
}

/**
* support more distros
 */
