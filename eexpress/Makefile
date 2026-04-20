.DEFAULT_GOAL := help

FIERY_IP := 10.10.96.103
PPD      := $(HOME)/fireman/assets/printer/ppd/EF604620.PPD

# ── Setup ────────────────────────────────────────────────────────────────────────

.PHONY: deps
deps: ## Install CUPS and discovery services (needs sudo)
	sudo dnf install -y cups avahi wsdd samba
	sudo systemctl enable --now avahi-daemon wsdd

.PHONY: setup-cups
setup-cups: deps ## Open CUPS to the LAN and enable printer sharing
	sudo sed -i 's|^Listen localhost:631|Listen *:631|' /etc/cups/cupsd.conf
	sudo grep -q 'Allow @LOCAL' /etc/cups/cupsd.conf || \
	    sudo python3 -c "\
t=open('/etc/cups/cupsd.conf').read(); \
t=t.replace('<Location />\n','<Location />\n  Order allow,deny\n  Allow @LOCAL\n'); \
open('/etc/cups/cupsd.conf','w').write(t)"
	sudo cupsctl --share-printers
	if sudo systemctl is-active --quiet firewalld; then \
	    sudo firewall-cmd --permanent --add-service=ipp --add-service=mdns && \
	    sudo firewall-cmd --permanent --add-port=3702/udp && \
	    sudo firewall-cmd --reload; \
	else \
	    sudo iptables -I INPUT -p tcp --dport 631 -j ACCEPT; \
	    sudo iptables -I INPUT -p udp --dport 5353 -j ACCEPT; \
	    sudo iptables -I INPUT -p udp --dport 3702 -j ACCEPT; \
	fi
	sudo systemctl restart cups

.PHONY: register-printer
register-printer: setup-cups ## Register EmberExpress and make it discoverable on the LAN
	sudo lpadmin -p EmberExpress -E \
		-v "ipp://$(FIERY_IP)/ipp/print" \
		-P $(PPD) \
		-o printer-is-shared=true
	sudo lpoptions -p EmberExpress \
		-o PageSize=Letter \
		-o EFPrintSize=LetterR \
		-o EFMediaType=Plain \
		-o EFMediaWeight=81_91 \
		-o EFPunchHoleType=None \
		-o EFOutputBin=Outbin1
	sudo cupsenable EmberExpress

# ── Day-to-day ───────────────────────────────────────────────────────────────

.PHONY: status
status: ## Show CUPS queue status
	lpstat -p EmberExpress

.PHONY: enable
enable: ## Re-enable the queue if CUPS disabled it after an error
	sudo cupsenable EmberExpress

.PHONY: remove-printer
remove-printer: ## Remove the EmberExpress queue
	sudo lpadmin -x EmberExpress

.PHONY: test
test: ## Send a test page
	lp -d EmberExpress /usr/share/cups/data/testprint

.PHONY: cups-log
cups-log: ## Follow the CUPS error log
	sudo journalctl -u cups --follow

.PHONY: options
options: ## Show the printer options
	lpoptions -p EmberExpress -l

# ── Help ─────────────────────────────────────────────────────────────────────

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

