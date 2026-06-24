// CONTROL DE PESTAÑAS
function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    document.getElementById(`tab-${tabId}`).classList.add('active');
    
    const buttons = document.querySelectorAll('.nav-btn');
    buttons.forEach(btn => {
        if (btn.getAttribute('onclick') && btn.getAttribute('onclick').includes(tabId)) {
            btn.classList.add('active');
        }
    });
}

// CONTROL DE SESIÓN Y USUARIOS
function checkSession() {
    const userStr = localStorage.getItem("user");
    const loginOverlay = document.getElementById("login-overlay");
    
    if (!userStr) {
        loginOverlay.classList.remove("hidden");
        return;
    }
    
    const user = JSON.parse(userStr);
    loginOverlay.classList.add("hidden");
    
    // Actualizar perfil en el Sidebar
    document.getElementById("user-display-name").innerText = user.username.toUpperCase();
    document.getElementById("user-display-role").innerText = user.role === 'admin' ? 'Dueño (Admin)' : 'Barbero';
    
    // Restringir visualización según rol
    const navDashboard = document.getElementById("nav-dashboard");
    const navTurnos = document.getElementById("nav-turnos");
    const navCargarGasto = document.getElementById("nav-cargar-gasto");
    const srvBarbero = document.getElementById("srv-barbero");
    
    if (user.role === 'barber') {
        // Ocultar tabs administrativas
        if (navDashboard) navDashboard.classList.add("hidden");
        if (navTurnos) navTurnos.classList.add("hidden");
        if (navCargarGasto) navCargarGasto.classList.add("hidden");
        
        // Cargar sólo carga de servicios
        switchTab('cargar-servicio');
        
        // Bloquear el select de barberos al barbero logueado
        setTimeout(() => {
            if (srvBarbero) {
                srvBarbero.value = user.barbero_id;
                srvBarbero.disabled = true;
            }
        }, 500);
    } else {
        // Admin ve todo
        if (navDashboard) navDashboard.classList.remove("hidden");
        if (navTurnos) navTurnos.classList.remove("hidden");
        if (navCargarGasto) navCargarGasto.classList.remove("hidden");
        
        if (srvBarbero) srvBarbero.disabled = false;
        
        switchTab('dashboard');
    }
    
    // Cargar datos
    loadDashboard();
    loadSelectOptions();
}

function submitLogin() {
    const username = document.getElementById("login-username").value.trim();
    const password = document.getElementById("login-password").value.trim();
    const errorMsg = document.getElementById("login-error");
    
    if (!username || !password) {
        alert("Por favor ingresa usuario y contraseña.");
        return;
    }
    
    fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
    })
    .then(res => {
        if (!res.ok) {
            throw new Error("Credenciales inválidas");
        }
        return res.json();
    })
    .then(data => {
        errorMsg.classList.add("hidden");
        localStorage.setItem("user", JSON.stringify(data));
        checkSession();
    })
    .catch(err => {
        errorMsg.classList.remove("hidden");
    });
}

function handleLoginKey(e) {
    if (e.key === 'Enter') {
        submitLogin();
    }
}

function logout() {
    localStorage.removeItem("user");
    location.reload();
}

// INICIALIZACIÓN
window.onload = function() {
    checkSession();
};

// CARGAR DATOS DEL DASHBOARD
function loadDashboard() {
    fetch('/api/dashboard')
        .then(res => res.json())
        .then(data => {
            // Actualizar KPIs
            document.getElementById('kpi-inversion').innerText = `$${data.inversion_total.toLocaleString('es-AR')}`;
            document.getElementById('kpi-porcentaje-amortizado').innerText = `${data.porcentaje_retorno}% Amortizado`;
            document.getElementById('amortization-progress').style.width = `${data.porcentaje_retorno}%`;
            document.getElementById('kpi-saldo-pendiente').innerText = `$${data.saldo_pendiente.toLocaleString('es-AR')}`;
            document.getElementById('kpi-bruto').innerText = `$${data.caja_mensual.toLocaleString('es-AR')}`;
            document.getElementById('kpi-gastos').innerText = `$${data.gastos_fijos.toLocaleString('es-AR')}`;

            // Actualizar Insumos
            const stockList = document.getElementById('insumos-stock-list');
            stockList.innerHTML = '';
            
            data.insumos.forEach(item => {
                let colorClass = 'normal';
                if (item.porcentaje <= 15) {
                    colorClass = 'critical';
                } else if (item.porcentaje < 50) {
                    colorClass = 'low';
                }
                
                const stockItem = document.createElement('div');
                stockItem.className = 'stock-item';
                stockItem.innerHTML = `
                    <div class="stock-item-info">
                        <span>${item.nombre}</span>
                        <span>${item.ml_actuales} ml / ${item.ml_totales} ml (${item.porcentaje}%)</span>
                    </div>
                    <div class="stock-progress-bg">
                        <div class="stock-progress-fill ${colorClass}" style="width: ${item.porcentaje}%"></div>
                    </div>
                `;
                stockList.appendChild(stockItem);
            });

            // Actualizar Alertas en pantalla
            const alertsDiv = document.getElementById('system-alerts');
            alertsDiv.innerHTML = '';
            data.alertas.forEach(msg => {
                const card = document.createElement('div');
                card.className = 'alert-card';
                card.innerHTML = `
                    <span>⚠️ ${msg}</span>
                    <button class="alert-close" onclick="this.parentElement.remove()">×</button>
                `;
                alertsDiv.appendChild(card);
            });

            // Actualizar Turnos Recientes
            const turnosTable = document.getElementById('turnos-table-body');
            if (turnosTable) {
                turnosTable.innerHTML = '';
                data.turnos_recientes.forEach(t => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td><strong>${t.cliente_nombre}</strong></td>
                        <td>${t.barbero_nombre}</td>
                        <td>${t.fecha_hora} hs</td>
                        <td><span class="status-badge ${t.estado.toLowerCase()}">${t.estado}</span></td>
                    `;
                    turnosTable.appendChild(tr);
                });
            }

            // Actualizar Items de Inversión Inicial (Dinámico con Editar/Eliminar)
            const invList = document.getElementById('inversion-items-list');
            if (invList) {
                invList.innerHTML = '';
                data.inversion_items.forEach(item => {
                    let emoji = '📦';
                    if (item.rubro === 'Mobiliario') emoji = '🪑';
                    else if (item.rubro === 'Infraestructura') emoji = '🏗️';
                    else if (item.rubro === 'Herramientas') emoji = '✂️';
                    
                    const div = document.createElement('div');
                    div.className = 'inv-item';
                    div.innerHTML = `
                        <span>${emoji} ${item.rubro} (${item.detalle})</span>
                        <div class="list-actions">
                            <strong style="margin-right: 8px;">$${item.monto.toLocaleString('es-AR')}</strong>
                            <span class="action-icon edit" onclick="editInversion(${item.id}, '${item.rubro}', '${item.detalle}', ${item.monto})" title="Editar">✏️</span>
                            <span class="action-icon delete" onclick="deleteInversion(${item.id})" title="Eliminar">❌</span>
                        </div>
                    `;
                    invList.appendChild(div);
                });
                
                document.getElementById('total-inversion-dynamic').innerText = `$${data.inversion_total.toLocaleString('es-AR')}`;
            }

            // Actualizar Gastos Operativos Detallados (Dinámico con Editar/Eliminar)
            const gstList = document.getElementById('gastos-items-list');
            if (gstList) {
                gstList.innerHTML = '';
                if (data.gastos_items.length === 0) {
                    gstList.innerHTML = `<p style="color: var(--text-muted); font-size:13px;">No hay gastos cargados en este mes.</p>`;
                }
                data.gastos_items.forEach(item => {
                    const div = document.createElement('div');
                    div.className = 'inv-item';
                    div.innerHTML = `
                        <span>💸 ${item.concepto}</span>
                        <div class="list-actions">
                            <strong style="margin-right: 8px;">$${item.monto.toLocaleString('es-AR')}</strong>
                            <span class="action-icon edit" onclick="editExpense(${item.id}, '${item.concepto}', ${item.monto})" title="Editar">✏️</span>
                            <span class="action-icon delete" onclick="deleteExpense(${item.id})" title="Eliminar">❌</span>
                        </div>
                    `;
                    gstList.appendChild(div);
                });
            }
        });
}

// CARGAR SELECTORES DE FORMULARIOS
function loadSelectOptions() {
    fetch('/api/barberos')
        .then(res => res.json())
        .then(data => {
            const barberSelect = document.getElementById('srv-barbero');
            if (barberSelect) {
                barberSelect.innerHTML = '';
                data.forEach(b => {
                    const opt = document.createElement('option');
                    opt.value = b.id;
                    opt.innerText = b.nombre;
                    barberSelect.appendChild(opt);
                });
            }
        });

    fetch('/api/insumos')
        .then(res => res.json())
        .then(data => {
            const insumoSelect = document.getElementById('srv-insumo');
            if (insumoSelect) {
                insumoSelect.innerHTML = '';
                data.forEach(i => {
                    const opt = document.createElement('option');
                    opt.value = i.id;
                    opt.innerText = i.nombre;
                    insumoSelect.appendChild(opt);
                });
            }
        });
}

// MOSTRAR/OCULTAR SECCIÓN DE INSUMOS SEGÚN SERVICIO
function toggleInsumoSection() {
    const servicio = document.getElementById('srv-nombre').value;
    const insumoSection = document.getElementById('insumo-section');
    const srvMonto = document.getElementById('srv-monto');
    
    if (servicio.includes("Tintura")) {
        insumoSection.classList.remove('hidden');
        srvMonto.value = 12000;
        
        const insumoSelect = document.getElementById('srv-insumo');
        if (servicio.includes("Negra")) {
            insumoSelect.value = 1;
        } else {
            insumoSelect.value = 2;
        }
    } else {
        insumoSection.classList.add('hidden');
        if (servicio === "Corte de pelo") srvMonto.value = 5000;
        if (servicio === "Recorte de barba") srvMonto.value = 3000;
        if (servicio === "Corte y Barba") srvMonto.value = 7000;
    }
}

// REGISTRAR SERVICIO
function submitService() {
    const barbero_id = document.getElementById('srv-barbero').value;
    const servicio_nombre = document.getElementById('srv-nombre').value;
    const monto_cobrado = document.getElementById('srv-monto').value;
    const metodo_pago = document.getElementById('srv-pago').value;
    
    const isTintura = !document.getElementById('insumo-section').classList.contains('hidden');
    const insumo_id = isTintura ? document.getElementById('srv-insumo').value : null;
    const ml_consumidos = isTintura ? document.getElementById('srv-ml').value : 0;

    fetch('/api/servicio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            barbero_id,
            servicio_nombre,
            monto_cobrado,
            metodo_pago,
            insumo_id,
            ml_consumidos
        })
    })
    .then(res => res.json())
    .then(data => {
        alert(data.message);
        if (data.alerta_insumo) {
            alert(data.alerta_insumo);
        }
        loadDashboard();
    });
}

// REGISTRAR GASTO
function submitExpense() {
    const concepto = document.getElementById('gst-concepto').value.trim();
    const monto = document.getElementById('gst-monto').value;
    
    if (!concepto || !monto) {
        alert("Por favor completa los campos del gasto.");
        return;
    }

    fetch('/api/gasto', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ concepto, monto })
    })
    .then(res => res.json())
    .then(data => {
        alert(data.message);
        document.getElementById('gst-concepto').value = '';
        document.getElementById('gst-monto').value = '';
        loadDashboard();
    });
}

// REGISTRAR INVERSIÓN INICIAL
function submitInversion() {
    const rubro = document.getElementById('inv-rubro').value;
    const detalle = document.getElementById('inv-detalle').value.trim();
    const monto = document.getElementById('inv-monto').value;
    
    if (!detalle || !monto) {
        alert("Por favor completa los campos del item de inversión.");
        return;
    }

    fetch('/api/inversion', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rubro, detalle, monto })
    })
    .then(res => res.json())
    .then(data => {
        alert(data.message);
        document.getElementById('inv-detalle').value = '';
        document.getElementById('inv-monto').value = '';
        loadDashboard();
    });
}

// ELIMINAR Y EDITAR INVERSIÓN
function deleteInversion(id) {
    if (!confirm("¿Estás seguro de que deseas eliminar este item de inversión?")) return;
    
    fetch(`/api/inversion/${id}`, { method: 'DELETE' })
        .then(res => res.json())
        .then(data => {
            alert(data.message);
            loadDashboard();
        });
}

function editInversion(id, currentRubro, currentDetalle, currentMonto) {
    const rubro = prompt("Modificar Rubro (Mobiliario, Infraestructura, Herramientas, Otros):", currentRubro);
    if (rubro === null) return;
    const detalle = prompt("Modificar Detalle del Bien:", currentDetalle);
    if (detalle === null) return;
    const montoStr = prompt("Modificar Monto ($):", currentMonto);
    if (montoStr === null) return;
    
    const monto = parseFloat(montoStr);
    if (!detalle.trim() || isNaN(monto) || monto <= 0) {
        alert("Datos inválidos. No se aplicaron cambios.");
        return;
    }
    
    fetch(`/api/inversion/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rubro, detalle, monto })
    })
    .then(res => res.json())
    .then(data => {
        alert(data.message);
        loadDashboard();
    });
}

// ELIMINAR Y EDITAR GASTO
function deleteExpense(id) {
    if (!confirm("¿Estás seguro de que deseas eliminar este gasto mensual?")) return;
    
    fetch(`/api/gasto/${id}`, { method: 'DELETE' })
        .then(res => res.json())
        .then(data => {
            alert(data.message);
            loadDashboard();
        });
}

function editExpense(id, currentConcepto, currentMonto) {
    const concepto = prompt("Modificar Concepto del Gasto:", currentConcepto);
    if (concepto === null) return;
    const montoStr = prompt("Modificar Monto ($):", currentMonto);
    if (montoStr === null) return;
    
    const monto = parseFloat(montoStr);
    if (!concepto.trim() || isNaN(monto) || monto <= 0) {
        alert("Datos inválidos. No se aplicaron cambios.");
        return;
    }
    
    fetch(`/api/gasto/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ concepto, monto })
    })
    .then(res => res.json())
    .then(data => {
        alert(data.message);
        loadDashboard();
    });
}

// EJECUTAR CIERRE MENSUAL
function runMonthlyClosure() {
    const mes_ano = document.getElementById('cierre-mes').value;
    
    fetch('/api/cierre', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mes_ano })
    })
    .then(res => res.json())
    .then(data => {
        const resultBox = document.getElementById('closure-result');
        resultBox.classList.remove('hidden');
        
        let comisionHtml = '';
        if (data.contingencia_comision_activa) {
            resultBox.classList.add('alert-active');
            comisionHtml = `<span style="color: var(--warning); font-weight: bold;">⚠️ Contingencia Activa: Los barberos cobraron 40% de comisiones</span> (la porción del 50% de la barbería no cubría los costos del local).`;
        } else {
            resultBox.classList.remove('alert-active');
            comisionHtml = `<span style="color: var(--success); font-weight: bold;">✅ Split Estándar 50/50 Activo</span> (los ingresos cubrieron con éxito los costos del local).`;
        }

        let reporteBarberosHtml = '<ul>';
        data.reporte_barberos.forEach(b => {
            reporteBarberosHtml += `
                <li><strong>${b.nombre}:</strong> Bruto generado: $${b.bruto_generado.toLocaleString('es-AR')} | Pago: $${b.payout_neto.toLocaleString('es-AR')} (${b.comision_porcentaje}%)</li>
            `;
        });
        reporteBarberosHtml += '</ul>';

        resultBox.innerHTML = `
            <h4>Resultado del Cierre Contable (${data.mes_ano})</h4>
            <p>${comisionHtml}</p>
            <p><strong>Caja Bruta Generada:</strong> $${data.total_bruto_generado.toLocaleString('es-AR')}</p>
            <p><strong>Gastos Totales del Local:</strong> $${data.total_gastos_local.toLocaleString('es-AR')} (Gastos Fijos: $${data.gastos_fijos.toLocaleString('es-AR')}, Insumos: $${data.gastos_insumos.toLocaleString('es-AR')})</p>
            <p><strong>Porción Retenida por Barbería:</strong> $${data.retencion_local_total.toLocaleString('es-AR')}</p>
            <p><strong>Ganancia Líquida del Dueño:</strong> $${data.ganancia_neta_dueno_bruta.toLocaleString('es-AR')}</p>
            <p><strong>Monto Amortizado al ROI este mes:</strong> $${data.monto_amortizado_este_mes.toLocaleString('es-AR')}</p>
            <p><strong>Saldo Pendiente de Inversión Inicial:</strong> $${data.saldo_pendiente_inversion.toLocaleString('es-AR')} (Recuperado el ${data.retorno_porcentaje}%)</p>
            <h5 style="margin-top: 12px; margin-bottom: 6px; color:#fff;">Liquidación Barberos:</h5>
            ${reporteBarberosHtml}
        `;
        
        loadDashboard();
    });
}

// SIMULADOR CHAT DE WHATSAPP
function sendChatMessage() {
    const input = document.getElementById('chat-input-msg');
    const msg = input.value.trim();
    if (!msg) return;
    
    const clientName = document.getElementById('chat-client-name').value;
    const clientPhone = document.getElementById('chat-client-phone').value;
    
    appendMessage(msg, 'user');
    input.value = '';
    
    fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            name: clientName,
            phone: clientPhone,
            message: msg
        })
    })
    .then(res => res.json())
    .then(data => {
        appendMessage(data.response, 'bot');
    });
}

function handleChatKey(e) {
    if (e.key === 'Enter') {
        sendChatMessage();
    }
}

function appendMessage(text, sender) {
    const messagesArea = document.getElementById('chat-messages');
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${sender}`;
    msgDiv.innerText = text;
    messagesArea.appendChild(msgDiv);
    messagesArea.scrollTop = messagesArea.scrollHeight;
}

function useSugerencia(text) {
    document.getElementById('chat-input-msg').value = text;
    sendChatMessage();
}
