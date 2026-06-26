let balanceChart = null;
let roiChart = null;

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

    // Cerrar menú móvil si está abierto
    const sidebar = document.querySelector('.sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');
    if (sidebar && sidebar.classList.contains('open')) {
        sidebar.classList.remove('open');
        if (backdrop) backdrop.classList.remove('active');
    }

    // Refrescar vistas dinámicamente al cambiar de pestaña
    if (tabId === 'agenda-turnos') {
        loadAgenda();
    } else if (tabId === 'cargar-servicio') {
        const userStr = localStorage.getItem("user");
        if (userStr) {
            const user = JSON.parse(userStr);
            if (user.role === 'barber') {
                loadBarberServices(user.barbero_id);
            }
        }
    } else if (tabId === 'dashboard') {
        loadDashboard();
    }
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
    
    const mobileRole = document.getElementById("mobile-user-role-lbl");
    if (mobileRole) {
        mobileRole.innerText = user.role === 'admin' ? 'Admin' : 'Barbero';
    }
    
    // Restringir visualización según rol
    const navDashboard = document.getElementById("nav-dashboard");
    const navCargarGasto = document.getElementById("nav-cargar-gasto");
    const navAgenda = document.getElementById("nav-agenda-turnos");
    const srvBarbero = document.getElementById("srv-barbero");
    
    if (user.role === 'barber') {
        // Ocultar tabs administrativas
        if (navDashboard) navDashboard.classList.add("hidden");
        if (navCargarGasto) navCargarGasto.classList.add("hidden");
        if (navAgenda) navAgenda.classList.remove("hidden");
        
        // Cargar por defecto la agenda de turnos propia
        switchTab('agenda-turnos');
        
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
        if (navCargarGasto) navCargarGasto.classList.remove("hidden");
        if (navAgenda) navAgenda.classList.remove("hidden");
        
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
    .then(async res => {
        const isJson = res.headers.get('content-type')?.includes('application/json');
        const data = isJson ? await res.json() : null;
        if (!res.ok) {
            const error = (data && data.message) || "Usuario o contraseña incorrectos";
            throw new Error(error);
        }
        return data;
    })
    .then(data => {
        errorMsg.classList.add("hidden");
        localStorage.setItem("user", JSON.stringify(data));
        checkSession();
    })
    .catch(err => {
        errorMsg.innerText = err.message;
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
    const userStr = localStorage.getItem("user");
    if (!userStr) return;
    const user = JSON.parse(userStr);

    if (user.role === 'barber') {
        // Para barberos, cargar únicamente sus servicios y agenda asignada (evitando fugas contables de la administración)
        const barberServicesCard = document.getElementById('barber-services-card');
        if (barberServicesCard) barberServicesCard.classList.remove('hidden');
        loadBarberServices(user.barbero_id);
        loadAgenda();
        return;
    }

    fetch('/api/dashboard')
        .then(res => {
            if (!res.ok) throw new Error("Error al obtener los datos del dashboard");
            return res.json();
        })
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

            // Actualizar Liquidación Estimada (Admin Only)
            const estimatedPayoutsCard = document.getElementById('admin-estimated-payouts-card');
            const estimatedPayoutsTable = document.getElementById('estimated-payouts-table-body');
            
            if (user.role === 'admin') {
                if (estimatedPayoutsCard) estimatedPayoutsCard.classList.remove('hidden');
                if (estimatedPayoutsTable) {
                    estimatedPayoutsTable.innerHTML = '';
                    if (!data.status_estimado || !data.status_estimado.reporte_barberos || data.status_estimado.reporte_barberos.length === 0) {
                        estimatedPayoutsTable.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--text-muted); padding: 24px;">No hay servicios aprobados para liquidar en este mes.</td></tr>`;
                    } else {
                        data.status_estimado.reporte_barberos.forEach(b => {
                            const tr = document.createElement('tr');
                            const totalPagar = b.payout_neto + b.propinas_digitales;
                            tr.innerHTML = `
                                <td><strong>${b.nombre}</strong></td>
                                <td>$${b.bruto_generado.toLocaleString('es-AR')}</td>
                                <td>${b.comision_porcentaje}%</td>
                                <td>$${b.payout_neto.toLocaleString('es-AR')}</td>
                                <td>$${b.propinas_digitales.toLocaleString('es-AR')}</td>
                                <td><strong style="color: var(--success);">$${totalPagar.toLocaleString('es-AR')}</strong></td>
                            `;
                            estimatedPayoutsTable.appendChild(tr);
                        });
                    }
                }
            } else {
                if (estimatedPayoutsCard) estimatedPayoutsCard.classList.add('hidden');
            }

            // Actualizar Servicios Pendientes de Auditoría (Admin Only)
            const auditTable = document.getElementById('audit-table-body');
            const adminAuditCard = document.getElementById('admin-audit-card');
            
            if (user.role === 'admin') {
                if (adminAuditCard) adminAuditCard.classList.remove('hidden');
                if (auditTable) {
                    auditTable.innerHTML = '';
                    if (!data.servicios_pendientes || data.servicios_pendientes.length === 0) {
                        auditTable.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding: 24px;">No hay servicios pendientes de auditoría.</td></tr>`;
                    } else {
                        data.servicios_pendientes.forEach(s => {
                            const tr = document.createElement('tr');
                            const insumoUsado = s.insumo_id ? `${s.ml_consumidos} ml` : '-';
                            tr.innerHTML = `
                                <td><strong>${s.barbero_nombre}</strong></td>
                                <td>${s.servicio_nombre}</td>
                                <td>$${s.monto_cobrado.toLocaleString('es-AR')}</td>
                                <td>${s.metodo_pago}</td>
                                <td>${insumoUsado}</td>
                                <td>${s.fecha}</td>
                                <td>
                                    <span class="action-icon approve" onclick="approveService(${s.id}, ${s.monto_cobrado})" title="Verificar y Aprobar" style="color: var(--success); cursor: pointer; margin-right: 12px; font-size: 16px;">✔️</span>
                                    <span class="action-icon reject" onclick="rejectService(${s.id})" title="Rechazar y Eliminar" style="color: var(--danger); cursor: pointer; font-size: 16px;">❌</span>
                                </td>
                            `;
                            auditTable.appendChild(tr);
                        });
                    }
                }
            } else {
                if (adminAuditCard) adminAuditCard.classList.add('hidden');
            }

            // Actualizar Historial de Servicios Auditados (Admin Only)
            const auditedTable = document.getElementById('audited-services-table-body');
            const adminAuditedCard = document.getElementById('admin-audited-services-card');
            
            if (user.role === 'admin') {
                if (adminAuditedCard) adminAuditedCard.classList.remove('hidden');
                if (auditedTable) {
                    auditedTable.innerHTML = '';
                    if (!data.servicios_aprobados || data.servicios_aprobados.length === 0) {
                        auditedTable.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding: 24px;">No hay servicios auditados en este mes.</td></tr>`;
                    } else {
                        data.servicios_aprobados.forEach(s => {
                            const tr = document.createElement('tr');
                            const insumoUsado = s.insumo_id ? `${s.ml_consumidos} ml` : '-';
                            tr.innerHTML = `
                                <td><strong>${s.barbero_nombre}</strong></td>
                                <td>${s.servicio_nombre}</td>
                                <td>$${s.monto_cobrado.toLocaleString('es-AR')}</td>
                                <td>${s.metodo_pago}</td>
                                <td>${insumoUsado}</td>
                                <td>${s.fecha}</td>
                                <td>
                                    <span class="action-icon edit" onclick="editAuditedService(${s.id}, ${s.monto_cobrado})" title="Editar Monto" style="color: var(--accent); cursor: pointer; margin-right: 12px; font-size: 16px;">✏️</span>
                                    <span class="action-icon reject" onclick="rejectService(${s.id})" title="Rechazar y Eliminar" style="color: var(--danger); cursor: pointer; font-size: 16px;">❌</span>
                                </td>
                            `;
                            auditedTable.appendChild(tr);
                        });
                    }
                }
            } else {
                if (adminAuditedCard) adminAuditedCard.classList.add('hidden');
            }

            // Para barberos, cargar sus propios servicios (sin montos)
            const barberServicesCard = document.getElementById('barber-services-card');
            if (user.role === 'barber') {
                if (barberServicesCard) barberServicesCard.classList.remove('hidden');
                loadBarberServices(user.barbero_id);
            } else {
                if (barberServicesCard) barberServicesCard.classList.add('hidden');
            }

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

            // Actualizar Gastos Operativos Detallados e Insumos/Herramientas
            const gstList = document.getElementById('gastos-items-list');
            const insGstList = document.getElementById('insumos-gastos-items-list');
            
            if (gstList && insGstList) {
                gstList.innerHTML = '';
                insGstList.innerHTML = '';
                
                let hasOps = false;
                let hasInsumos = false;
                
                const insumoKeywords = [
                    "reposicion", "reposición", "tintura", "shampoo", "champu", 
                    "champú", "crema", "locion", "loción", "insumo", "producto", 
                    "tijera", "secador", "patillera", "peine", "maquina", "máquina", 
                    "navaja", "bucleadora", "herramienta", "insumos"
                ];
                
                data.gastos_items.forEach(item => {
                    const conceptoLower = item.concepto.toLowerCase();
                    const isInsumo = insumoKeywords.some(keyword => conceptoLower.includes(keyword));
                    
                    const div = document.createElement('div');
                    div.className = 'inv-item';
                    div.innerHTML = `
                        <span>${isInsumo ? '📦' : '💸'} ${item.concepto}</span>
                        <div class="list-actions">
                            <strong style="margin-right: 8px;">$${item.monto.toLocaleString('es-AR')}</strong>
                            <span class="action-icon edit" onclick="editExpense(${item.id}, '${item.concepto}', ${item.monto})" title="Editar">✏️</span>
                            <span class="action-icon delete" onclick="deleteExpense(${item.id})" title="Eliminar">❌</span>
                        </div>
                    `;
                    
                    if (isInsumo) {
                        insGstList.appendChild(div);
                        hasInsumos = true;
                    } else {
                        gstList.appendChild(div);
                        hasOps = true;
                    }
                });
                
                if (!hasOps) {
                    gstList.innerHTML = `<p style="color: var(--text-muted); font-size:13px;">No hay gastos operativos cargados en este mes.</p>`;
                }
                if (!hasInsumos) {
                    insGstList.innerHTML = `<p style="color: var(--text-muted); font-size:13px;">No hay compras de insumos o herramientas cargadas en este mes.</p>`;
                }
            }
            updateCharts(data);
            loadAgenda();
        })
        .catch(err => {
            console.error("Error al cargar dashboard: ", err);
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
            window.insumosData = data; // Guardar en caché global
            
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

            const repSelect = document.getElementById('rep-insumo');
            if (repSelect) {
                repSelect.innerHTML = '';
                data.forEach(i => {
                    const opt = document.createElement('option');
                    opt.value = i.id;
                    opt.innerText = i.nombre;
                    repSelect.appendChild(opt);
                });
                onInsumoChange(); // Autocompletar primer elemento
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

    if (!monto_cobrado || parseFloat(monto_cobrado) <= 0) {
        alert("Por favor ingresa un monto cobrado válido.");
        return;
    }

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
    .then(async res => {
        const isJson = res.headers.get('content-type')?.includes('application/json');
        const data = isJson ? await res.json() : null;
        if (!res.ok) {
            const error = (data && data.error) || 'Error al registrar servicio';
            throw new Error(error);
        }
        return data;
    })
    .then(data => {
        alert(data.message);
        if (data.alerta_insumo) {
            alert(data.alerta_insumo);
        }
        loadDashboard();
    })
    .catch(err => {
        alert("Error al registrar servicio: " + err.message);
    });
}

// REGISTRAR GASTO
function submitExpense() {
    const concepto = document.getElementById('gst-concepto').value.trim();
    const monto = document.getElementById('gst-monto').value;
    
    if (!concepto || !monto || parseFloat(monto) <= 0) {
        alert("Por favor completa los campos del gasto con un valor mayor a cero.");
        return;
    }

    fetch('/api/gasto', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ concepto, monto })
    })
    .then(async res => {
        const isJson = res.headers.get('content-type')?.includes('application/json');
        const data = isJson ? await res.json() : null;
        if (!res.ok) {
            const error = (data && data.error) || 'Error al registrar gasto';
            throw new Error(error);
        }
        return data;
    })
    .then(data => {
        alert(data.message);
        document.getElementById('gst-concepto').value = '';
        document.getElementById('gst-monto').value = '';
        loadDashboard();
    })
    .catch(err => {
        alert("Error al registrar gasto: " + err.message);
    });
}

// REGISTRAR INVERSIÓN INICIAL
function submitInversion() {
    const rubro = document.getElementById('inv-rubro').value;
    const detalle = document.getElementById('inv-detalle').value.trim();
    const monto = document.getElementById('inv-monto').value;
    
    if (!detalle || !monto || parseFloat(monto) <= 0) {
        alert("Por favor completa los campos de inversión con un valor mayor a cero.");
        return;
    }

    fetch('/api/inversion', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rubro, detalle, monto })
    })
    .then(async res => {
        const isJson = res.headers.get('content-type')?.includes('application/json');
        const data = isJson ? await res.json() : null;
        if (!res.ok) {
            const error = (data && data.error) || 'Error al registrar inversión';
            throw new Error(error);
        }
        return data;
    })
    .then(data => {
        alert(data.message);
        document.getElementById('inv-detalle').value = '';
        document.getElementById('inv-monto').value = '';
        loadDashboard();
    })
    .catch(err => {
        alert("Error al registrar inversión: " + err.message);
    });
}

// ELIMINAR Y EDITAR INVERSIÓN
function deleteInversion(id) {
    if (!confirm("¿Estás seguro de que deseas eliminar este item de inversión?")) return;
    
    fetch(`/api/inversion/${id}`, { method: 'DELETE' })
        .then(async res => {
            const isJson = res.headers.get('content-type')?.includes('application/json');
            const data = isJson ? await res.json() : null;
            if (!res.ok) throw new Error((data && data.error) || 'Error al eliminar inversión');
            return data;
        })
        .then(data => {
            alert(data.message);
            loadDashboard();
        })
        .catch(err => alert("Error: " + err.message));
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
    .then(async res => {
        const isJson = res.headers.get('content-type')?.includes('application/json');
        const data = isJson ? await res.json() : null;
        if (!res.ok) throw new Error((data && data.error) || 'Error al actualizar inversión');
        return data;
    })
    .then(data => {
        alert(data.message);
        loadDashboard();
    })
    .catch(err => alert("Error: " + err.message));
}

// ELIMINAR Y EDITAR GASTO
function deleteExpense(id) {
    if (!confirm("¿Estás seguro de que deseas eliminar este gasto mensual?")) return;
    
    fetch(`/api/gasto/${id}`, { method: 'DELETE' })
        .then(async res => {
            const isJson = res.headers.get('content-type')?.includes('application/json');
            const data = isJson ? await res.json() : null;
            if (!res.ok) throw new Error((data && data.error) || 'Error al eliminar gasto');
            return data;
        })
        .then(data => {
            alert(data.message);
            loadDashboard();
        })
        .catch(err => alert("Error: " + err.message));
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
    .then(async res => {
        const isJson = res.headers.get('content-type')?.includes('application/json');
        const data = isJson ? await res.json() : null;
        if (!res.ok) throw new Error((data && data.error) || 'Error al actualizar gasto');
        return data;
    })
    .then(data => {
        alert(data.message);
        loadDashboard();
    })
    .catch(err => alert("Error: " + err.message));
}

// EJECUTAR CIERRE MENSUAL
function runMonthlyClosure() {
    const mes_ano = document.getElementById('cierre-mes').value;
    
    fetch('/api/cierre', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mes_ano })
    })
    .then(async res => {
        const isJson = res.headers.get('content-type')?.includes('application/json');
        const data = isJson ? await res.json() : null;
        if (!res.ok) throw new Error((data && data.error) || 'Error al ejecutar cierre contable');
        return data;
    })
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
    })
    .catch(err => {
        alert("Error al ejecutar cierre: " + err.message);
    });
}



// CARGAR AGENDA DE TURNOS (ADMIN O FILTRADO POR BARBERO)
function loadAgenda() {
    const userStr = localStorage.getItem("user");
    if (!userStr) return;
    const user = JSON.parse(userStr);
    
    const actionsHeader = document.getElementById("agenda-actions-header");
    const isAdmin = user.role === 'admin';
    if (actionsHeader) {
        if (isAdmin) {
            actionsHeader.classList.remove("hidden");
        } else {
            actionsHeader.classList.add("hidden");
        }
    }
    
    let url = '/api/turnos';
    if (user.role === 'barber') {
        url += `?barbero_id=${user.barbero_id}`;
        const titleEl = document.getElementById("agenda-title");
        const descEl = document.getElementById("agenda-desc");
        if (titleEl) titleEl.innerText = "Mis Turnos Asignados";
        if (descEl) descEl.innerText = "Listado de clientes agendados para tu atención";
    } else {
        const titleEl = document.getElementById("agenda-title");
        const descEl = document.getElementById("agenda-desc");
        if (titleEl) titleEl.innerText = "Agenda General de Turnos";
        if (descEl) descEl.innerText = "Listado completo de reservas activas en la barbería";
    }
    
    fetch(url)
        .then(res => res.json())
        .then(data => {
            const tbody = document.getElementById("agenda-table-body");
            if (tbody) {
                tbody.innerHTML = '';
                if (data.length === 0) {
                    const cols = isAdmin ? 6 : 5;
                    tbody.innerHTML = `<tr><td colspan="${cols}" style="text-align:center; color:var(--text-muted); padding: 24px;">No hay turnos registrados en la agenda.</td></tr>`;
                    return;
                }
                data.forEach(t => {
                    const tr = document.createElement("tr");
                    let actionsTd = '';
                    if (isAdmin) {
                        actionsTd = `<td><button class="delete-btn" onclick="deleteTurno(${t.id})" style="background: none; border: none; cursor: pointer; color: var(--danger); font-size: 16px;">❌</button></td>`;
                    }
                    tr.innerHTML = `
                        <td><strong>${t.cliente_nombre}</strong></td>
                        <td>${t.cliente_telefono}</td>
                        <td>${t.barbero_nombre}</td>
                        <td>${t.fecha_hora} hs</td>
                        <td><span class="status-badge ${t.estado.toLowerCase()}">${t.estado}</span></td>
                        ${actionsTd}
                    `;
                    tbody.appendChild(tr);
                });
            }
        });
}

function deleteTurno(id) {
    if (!confirm("¿Estás seguro de que deseas eliminar este turno de la agenda?")) return;
    
    fetch(`/api/turno/${id}`, {
        method: 'DELETE'
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'success') {
            alert(data.message);
            loadAgenda();
            // Si hay loadDashboard definido para refrescar métricas
            if (typeof loadDashboard === 'function') {
                loadDashboard();
            }
        } else {
            alert("Error al eliminar turno: " + data.error);
        }
    })
    .catch(err => {
        alert("Error al conectar con el servidor: " + err);
    });
}

// AUDITORÍA DE SERVICIOS (ADMIN ONLY)
function approveService(id, currentMonto) {
    const finalMontoStr = prompt("Confirmar o corregir el monto cobrado para este servicio ($):", currentMonto);
    if (finalMontoStr === null) return; // canceló
    
    const finalMonto = parseFloat(finalMontoStr);
    if (isNaN(finalMonto) || finalMonto <= 0) {
        alert("Por favor ingresa un monto válido.");
        return;
    }
    
    fetch(`/api/servicio/aprobar/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ monto_cobrado: finalMonto })
    })
    .then(async res => {
        const isJson = res.headers.get('content-type')?.includes('application/json');
        const data = isJson ? await res.json() : null;
        if (!res.ok) {
            const error = (data && data.error) || res.statusText || 'Error en el servidor';
            throw new Error(error);
        }
        return data;
    })
    .then(data => {
        alert(data.message);
        loadDashboard();
    })
    .catch(err => {
        alert("Error al aprobar servicio: " + err.message);
    });
}

function rejectService(id) {
    if (!confirm("¿Estás seguro de que deseas rechazar y eliminar este servicio? El barbero tendrá que cargarlo de nuevo.")) return;
    
    fetch(`/api/servicio/rechazar/${id}`, {
        method: 'POST'
    })
    .then(async res => {
        const isJson = res.headers.get('content-type')?.includes('application/json');
        const data = isJson ? await res.json() : null;
        if (!res.ok) {
            const error = (data && data.error) || res.statusText || 'Error en el servidor';
            throw new Error(error);
        }
        return data;
    })
    .then(data => {
        alert(data.message);
        loadDashboard();
    })
    .catch(err => {
        alert("Error al rechazar servicio: " + err.message);
    });
}

// EDITAR SERVICIO AUDITADO (ADMIN ONLY)
function editAuditedService(id, currentMonto) {
    const finalMontoStr = prompt("Modificar el monto cobrado para este servicio auditado ($):", currentMonto);
    if (finalMontoStr === null) return;
    
    const finalMonto = parseFloat(finalMontoStr);
    if (isNaN(finalMonto) || finalMonto <= 0) {
        alert("Por favor ingresa un monto válido.");
        return;
    }
    
    fetch(`/api/servicio/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ monto_cobrado: finalMonto })
    })
    .then(async res => {
        const isJson = res.headers.get('content-type')?.includes('application/json');
        const data = isJson ? await res.json() : null;
        if (!res.ok) {
            throw new Error((data && data.error) || 'Error al actualizar servicio');
        }
        return data;
    })
    .then(data => {
        alert(data.message);
        loadDashboard();
    })
    .catch(err => {
        alert("Error al editar servicio: " + err.message);
    });
}

// CARGAR SERVICIOS PROPIOS DEL BARBERO (SIN MONTOS)
function loadBarberServices(barberoId) {
    fetch(`/api/barbero/servicios?barbero_id=${barberoId}`)
        .then(res => {
            if (!res.ok) throw new Error("Error al obtener tus servicios.");
            return res.json();
        })
        .then(data => {
            const tbody = document.getElementById("barber-services-table-body");
            if (tbody) {
                tbody.innerHTML = '';
                if (data.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--text-muted); padding: 24px;">No has registrado servicios este mes.</td></tr>`;
                    return;
                }
                data.forEach(s => {
                    const tr = document.createElement("tr");
                    const statusText = s.aprobado === 1 ? '<span style="color: var(--success); font-weight: bold;">✅ Auditado y Aprobado</span>' : '<span style="color: var(--warning); font-weight: bold;">⏳ Pendiente de Auditoría</span>';
                    const insumoUsado = s.insumo_id ? `${s.ml_consumidos} ml` : '-';
                    tr.innerHTML = `
                        <td><strong>${s.servicio_nombre}</strong></td>
                        <td>${s.metodo_pago}</td>
                        <td>${insumoUsado}</td>
                        <td>${s.fecha}</td>
                        <td>${statusText}</td>
                    `;
                    tbody.appendChild(tr);
                });
            }
        })
        .catch(err => {
            console.error("Error al cargar servicios del barbero:", err);
        });
}

// AUTOCOMPLETAR CAPACIDAD DE INSUMO AL SELECCIONAR
function onInsumoChange() {
    const select = document.getElementById('rep-insumo');
    const inputMl = document.getElementById('rep-ml-unidad');
    if (!select || !inputMl || !window.insumosData) return;
    
    const selectedId = parseInt(select.value);
    const insumo = window.insumosData.find(i => i.id === selectedId);
    if (insumo) {
        const nombre = insumo.nombre.toLowerCase();
        if (nombre.includes("tintura")) {
            inputMl.value = 250;
        } else if (nombre.includes("champú") || nombre.includes("champu")) {
            inputMl.value = 1000;
        } else if (nombre.includes("loción") || nombre.includes("locion")) {
            inputMl.value = 500;
        } else {
            inputMl.value = 250; // Fallback por defecto
        }
    }
}

// ENVIAR REPOSICIÓN DE INSUMOS
function submitReplenishment() {
    const insumo_id = document.getElementById('rep-insumo').value;
    const unidades = document.getElementById('rep-unidades').value;
    const ml_por_unidad = document.getElementById('rep-ml-unidad').value;
    const precio_total = document.getElementById('rep-precio-total').value;

    if (!insumo_id || !unidades || !ml_por_unidad || !precio_total) {
        alert("Por favor completa todos los campos del formulario de reposición.");
        return;
    }

    if (parseInt(unidades) <= 0 || parseFloat(ml_por_unidad) <= 0 || parseFloat(precio_total) <= 0) {
        alert("Los valores de unidades, mililitros y precio deben ser mayores a cero.");
        return;
    }

    fetch('/api/insumo/reponer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            insumo_id,
            unidades,
            ml_por_unidad,
            precio_total
        })
    })
    .then(async res => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Error en la reposición");
        
        alert(data.message);
        
        // Limpiar inputs
        document.getElementById('rep-unidades').value = 1;
        document.getElementById('rep-ml-unidad').value = '';
        document.getElementById('rep-precio-total').value = '';
        
        // Recargar Dashboard y actualizar selectores
        loadDashboard();
        loadSelectOptions();
    })
    .catch(err => {
        alert("Error al registrar reposición: " + err.message);
        console.error(err);
    });
}

// DIBUJAR GRÁFICOS CONTABLES CON CHART.JS
function updateCharts(data) {
    const ctxBalance = document.getElementById('chart-balance');
    const ctxRoi = document.getElementById('chart-roi');

    if (!ctxBalance || !ctxRoi) return;

    // Destruir gráficos anteriores si existen
    if (balanceChart) balanceChart.destroy();
    if (roiChart) roiChart.destroy();

    // 1. Gráfico de Balance (Barra Comparativa)
    const bruto = data.caja_mensual;
    const fijos = data.status_estimado ? data.status_estimado.gastos_fijos : data.gastos_fijos;
    const insumos = data.status_estimado ? data.status_estimado.gastos_insumos : 0;
    const totalGastos = fijos + insumos;

    balanceChart = new Chart(ctxBalance, {
        type: 'bar',
        data: {
            labels: ['Ingresos Brutos', 'Gastos Fijos', 'Costo Insumos', 'Total Gastos'],
            datasets: [{
                label: 'Monto ($)',
                data: [bruto, fijos, insumos, totalGastos],
                backgroundColor: [
                    'rgba(16, 185, 129, 0.6)', // success (green)
                    'rgba(245, 158, 11, 0.6)', // warning (orange)
                    'rgba(6, 182, 212, 0.6)',  // accent (cyan)
                    'rgba(239, 68, 68, 0.6)'    // danger (red)
                ],
                borderColor: [
                    '#10b981',
                    '#f59e0b',
                    '#06b6d4',
                    '#ef4444'
                ],
                borderWidth: 1.5,
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return ` $${context.raw.toLocaleString('es-AR')}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: {
                        color: '#9ca3af',
                        callback: function(value) { return '$' + value.toLocaleString('es-AR'); }
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#9ca3af' }
                }
            }
        }
    });

    // 2. Gráfico de ROI (Dona Interactiva)
    const amortizado = data.total_amortizado;
    const pendiente = data.saldo_pendiente;

    roiChart = new Chart(ctxRoi, {
        type: 'doughnut',
        data: {
            labels: ['Capital Amortizado', 'Capital Pendiente'],
            datasets: [{
                data: [amortizado, pendiente],
                backgroundColor: [
                    'rgba(16, 185, 129, 0.6)', // success (green)
                    'rgba(239, 68, 68, 0.6)'    // danger (red)
                ],
                borderColor: [
                    '#10b981',
                    '#ef4444'
                ],
                borderWidth: 1.5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#9ca3af', padding: 16 }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const val = context.raw;
                            const total = amortizado + pendiente;
                            const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
                            return ` $${val.toLocaleString('es-AR')} (${pct}%)`;
                        }
                    }
                }
            },
            cutout: '65%'
        }
    });
}

// CONTROL DE MENÚ MÓVIL DESPLEGABLE (SIDEBAR DRAWER)
function toggleMobileMenu() {
    const sidebar = document.querySelector('.sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');
    if (sidebar) {
        sidebar.classList.toggle('open');
    }
    if (backdrop) {
        backdrop.classList.toggle('active');
    }
}

// IA COPILOT CHAT CLIENT
function sendIaChatMessage() {
    const input = document.getElementById("ia-chat-input");
    const message = input.value.trim();
    if (!message) return;

    // Renderizar mensaje del usuario
    appendIaMessage(message, "user");
    input.value = "";

    // Renderizar indicador de escritura
    const messagesBox = document.getElementById("ia-chat-messages");
    const typingBubble = document.createElement("div");
    typingBubble.className = "message bot";
    typingBubble.id = "ia-typing-bubble";
    typingBubble.style = "align-self: flex-start; background-color: var(--bg-dark); border: 1px solid var(--card-border); border-radius: 12px; border-top-left-radius: 0; padding: 12px 16px; color: var(--text-muted); max-width: 85%; font-size: 13px; line-height: 1.5; font-style: italic;";
    typingBubble.innerHTML = "🤖 Escribiendo...";
    messagesBox.appendChild(typingBubble);
    messagesBox.scrollTop = messagesBox.scrollHeight;

    fetch("/api/ia/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message })
    })
    .then(res => {
        if (!res.ok) throw new Error("Error de red");
        return res.json();
    })
    .then(data => {
        // Eliminar indicador de escritura
        const bubble = document.getElementById("ia-typing-bubble");
        if (bubble) bubble.remove();

        // Renderizar respuesta formateada
        appendIaMessage(data.response, "bot");
    })
    .catch(err => {
        const bubble = document.getElementById("ia-typing-bubble");
        if (bubble) bubble.remove();
        appendIaMessage("🤖 Disculpa, he tenido un problema al procesar tu consulta. Inténtalo de nuevo.", "bot");
    });
}

function appendIaMessage(text, sender) {
    const messagesBox = document.getElementById("ia-chat-messages");
    if (!messagesBox) return;

    const bubble = document.createElement("div");
    bubble.className = `message ${sender}`;
    
    // Convertir saltos de línea y formateo markdown simple
    let formattedText = text
        .replace(/\n/g, "<br>")
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.*?)\*/g, "<em>$1</em>");
        
    if (sender === "user") {
        bubble.style = "align-self: flex-end; background-color: var(--primary); border-radius: 12px; border-top-right-radius: 0; padding: 12px 16px; color: #fff; max-width: 85%; font-size: 13px; line-height: 1.5;";
        bubble.innerHTML = formattedText;
    } else {
        bubble.style = "align-self: flex-start; background-color: var(--bg-dark); border: 1px solid var(--card-border); border-radius: 12px; border-top-left-radius: 0; padding: 12px 16px; color: #fff; max-width: 85%; font-size: 13px; line-height: 1.5;";
        bubble.innerHTML = formattedText;
    }

    messagesBox.appendChild(bubble);
    messagesBox.scrollTop = messagesBox.scrollHeight;
}

function handleIaChatKey(event) {
    if (event.key === "Enter") {
        sendIaChatMessage();
    }
}

function sendIaSuggestion(text) {
    const input = document.getElementById("ia-chat-input");
    if (input) {
        input.value = text;
        sendIaChatMessage();
    }
}
