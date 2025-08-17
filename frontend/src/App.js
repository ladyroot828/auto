import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './components/ui/card';
import { Button } from './components/ui/button';
import { Input } from './components/ui/input';
import { Label } from './components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './components/ui/tabs';
import { Badge } from './components/ui/badge';
import { Alert, AlertDescription } from './components/ui/alert';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './components/ui/table';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from './components/ui/dialog';
import { Textarea } from './components/ui/textarea';
import { Progress } from './components/ui/progress';
import { Separator } from './components/ui/separator';
import { 
  Phone, 
  Users, 
  Play, 
  Square, 
  Trash2, 
  Plus, 
  Settings, 
  BarChart3,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  AlertCircle,
  Target,
  UserPlus
} from 'lucide-react';
import './App.css';

const API_BASE = process.env.REACT_APP_BACKEND_URL;

function App() {
  const [accounts, setAccounts] = useState([]);
  const [automationLogs, setAutomationLogs] = useState([]);
  const [stats, setStats] = useState({ today: {}, last_24h: {} });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  // Form states
  const [phoneNumber, setPhoneNumber] = useState('');
  const [verificationCode, setVerificationCode] = useState('');
  const [showCodeInput, setShowCodeInput] = useState(false);
  const [currentPhone, setCurrentPhone] = useState('');
  
  // Automation states
  const [sourceGroups, setSourceGroups] = useState('');
  const [targetGroup, setTargetGroup] = useState('');
  const [delayMin, setDelayMin] = useState(6);
  const [delayMax, setDelayMax] = useState(15);
  const [maxMembers, setMaxMembers] = useState(100);
  const [activeAutomation, setActiveAutomation] = useState(null);

  useEffect(() => {
    loadData();
    // Auto-refresh every 10 seconds
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [accountsRes, logsRes, statsRes] = await Promise.all([
        axios.get(`${API_BASE}/api/accounts`),
        axios.get(`${API_BASE}/api/automation/logs`),
        axios.get(`${API_BASE}/api/automation/stats`)
      ]);
      
      setAccounts(accountsRes.data);
      setAutomationLogs(logsRes.data);
      setStats(statsRes.data);
    } catch (err) {
      console.error('Erro ao carregar dados:', err);
    }
  };

  const showMessage = (message, type = 'success') => {
    if (type === 'success') {
      setSuccess(message);
      setError('');
      setTimeout(() => setSuccess(''), 3000);
    } else {
      setError(message);
      setSuccess('');
      setTimeout(() => setError(''), 5000);
    }
  };

  const requestVerificationCode = async () => {
    if (!phoneNumber.trim()) {
      showMessage('Digite um número de telefone válido', 'error');
      return;
    }

    setLoading(true);
    try {
      await axios.post(`${API_BASE}/api/accounts/request-code`, {
        phone_number: phoneNumber
      });
      
      setShowCodeInput(true);
      setCurrentPhone(phoneNumber);
      showMessage('Código de verificação enviado! Verifique seu Telegram.');
    } catch (err) {
      showMessage(err.response?.data?.detail || 'Erro ao solicitar código', 'error');
    } finally {
      setLoading(false);
    }
  };

  const verifyCode = async () => {
    if (!verificationCode.trim()) {
      showMessage('Digite o código de verificação', 'error');
      return;
    }

    setLoading(true);
    try {
      await axios.post(`${API_BASE}/api/accounts/verify-code`, {
        phone_number: currentPhone,
        code: verificationCode
      });
      
      setShowCodeInput(false);
      setPhoneNumber('');
      setVerificationCode('');
      setCurrentPhone('');
      showMessage('Conta autenticada com sucesso!');
      loadData();
    } catch (err) {
      showMessage(err.response?.data?.detail || 'Código inválido', 'error');
    } finally {
      setLoading(false);
    }
  };

  const activateAccount = async (accountId) => {
    try {
      await axios.post(`${API_BASE}/api/accounts/${accountId}/activate`);
      showMessage('Conta ativada!');
      loadData();
    } catch (err) {
      showMessage('Erro ao ativar conta', 'error');
    }
  };

  const deleteAccount = async (accountId) => {
    if (!window.confirm('Tem certeza que deseja remover esta conta?')) return;
    
    try {
      await axios.delete(`${API_BASE}/api/accounts/${accountId}`);
      showMessage('Conta removida!');
      loadData();
    } catch (err) {
      showMessage('Erro ao remover conta', 'error');
    }
  };

  const startAutomation = async () => {
    const activeAccount = accounts.find(acc => acc.is_active);
    if (!activeAccount) {
      showMessage('Selecione uma conta ativa primeiro', 'error');
      return;
    }

    if (!sourceGroups.trim() || !targetGroup.trim()) {
      showMessage('Preencha os grupos de origem e destino', 'error');
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post(`${API_BASE}/api/automation/start`, {
        account_id: activeAccount.id,
        source_groups: sourceGroups.split('\n').map(g => g.trim()).filter(g => g),
        target_group: targetGroup.trim(),
        delay_min: delayMin,
        delay_max: delayMax,
        max_members: maxMembers
      });

      setActiveAutomation(response.data.log_id);
      showMessage('Automação iniciada!');
      loadData();
    } catch (err) {
      showMessage(err.response?.data?.detail || 'Erro ao iniciar automação', 'error');
    } finally {
      setLoading(false);
    }
  };

  const stopAutomation = async () => {
    if (!activeAutomation) return;

    try {
      await axios.post(`${API_BASE}/api/automation/${activeAutomation}/stop`);
      setActiveAutomation(null);
      showMessage('Automação parada!');
      loadData();
    } catch (err) {
      showMessage('Erro ao parar automação', 'error');
    }
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      'pending': { variant: 'secondary', icon: Clock, text: 'Pendente' },
      'code_requested': { variant: 'secondary', icon: Clock, text: 'Código Solicitado' },
      'authenticated': { variant: 'default', icon: CheckCircle, text: 'Autenticado' },
      'running': { variant: 'default', icon: Loader2, text: 'Executando' },
      'completed': { variant: 'secondary', icon: CheckCircle, text: 'Concluído' },
      'stopped': { variant: 'destructive', icon: Square, text: 'Parado' },
      'failed': { variant: 'destructive', icon: XCircle, text: 'Falhou' }
    };

    const config = statusConfig[status] || statusConfig.pending;
    const Icon = config.icon;

    return (
      <Badge variant={config.variant} className="flex items-center gap-1">
        <Icon className="w-3 h-3" />
        {config.text}
      </Badge>
    );
  };

  const activeAccount = accounts.find(acc => acc.is_active);
  const runningLogs = automationLogs.filter(log => log.status === 'running');

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-blue-600 rounded-lg">
                <Target className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-900">Telegram Automation</h1>
                <p className="text-sm text-slate-600">Painel de Automação de Grupos</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              {activeAccount && (
                <Badge variant="default" className="px-3 py-1">
                  <Phone className="w-3 h-3 mr-1" />
                  {activeAccount.phone_number}
                </Badge>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Alerts */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-4">
        {error && (
          <Alert className="mb-4 border-red-200 bg-red-50">
            <AlertCircle className="h-4 w-4 text-red-600" />
            <AlertDescription className="text-red-800">{error}</AlertDescription>
          </Alert>
        )}
        {success && (
          <Alert className="mb-4 border-green-200 bg-green-50">
            <CheckCircle className="h-4 w-4 text-green-600" />
            <AlertDescription className="text-green-800">{success}</AlertDescription>
          </Alert>
        )}
      </div>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Tabs defaultValue="accounts" className="space-y-6">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="accounts" className="flex items-center gap-2">
              <Users className="w-4 h-4" />
              Contas
            </TabsTrigger>
            <TabsTrigger value="automation" className="flex items-center gap-2">
              <Play className="w-4 h-4" />
              Automação
            </TabsTrigger>
            <TabsTrigger value="reports" className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4" />
              Relatórios
            </TabsTrigger>
            <TabsTrigger value="settings" className="flex items-center gap-2">
              <Settings className="w-4 h-4" />
              Configurações
            </TabsTrigger>
          </TabsList>

          {/* Accounts Tab */}
          <TabsContent value="accounts" className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Add Account Form */}
              <Card className="lg:col-span-1">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Plus className="w-5 h-5" />
                    Adicionar Conta
                  </CardTitle>
                  <CardDescription>
                    Conecte uma nova conta do Telegram
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {!showCodeInput ? (
                    <>
                      <div className="space-y-2">
                        <Label htmlFor="phone">Número do Telefone</Label>
                        <Input
                          id="phone"
                          placeholder="+55 11 99999-9999"
                          value={phoneNumber}
                          onChange={(e) => setPhoneNumber(e.target.value)}
                        />
                      </div>
                      <Button 
                        onClick={requestVerificationCode}
                        disabled={loading}
                        className="w-full"
                      >
                        {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Phone className="w-4 h-4 mr-2" />}
                        Solicitar Código
                      </Button>
                    </>
                  ) : (
                    <>
                      <div className="space-y-2">
                        <Label htmlFor="code">Código de Verificação</Label>
                        <Input
                          id="code"
                          placeholder="12345"
                          value={verificationCode}
                          onChange={(e) => setVerificationCode(e.target.value)}
                        />
                        <p className="text-sm text-slate-600">
                          Código enviado para {currentPhone}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <Button 
                          onClick={verifyCode}
                          disabled={loading}
                          className="flex-1"
                        >
                          {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <CheckCircle className="w-4 h-4 mr-2" />}
                          Verificar
                        </Button>
                        <Button 
                          variant="outline"
                          onClick={() => {
                            setShowCodeInput(false);
                            setVerificationCode('');
                          }}
                        >
                          Cancelar
                        </Button>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>

              {/* Accounts List */}
              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle>Contas Conectadas</CardTitle>
                  <CardDescription>
                    {accounts.length} conta(s) configurada(s)
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {accounts.length === 0 ? (
                    <div className="text-center py-6 text-slate-500">
                      <Phone className="w-12 h-12 mx-auto mb-2 opacity-50" />
                      <p>Nenhuma conta conectada ainda</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {accounts.map((account) => (
                        <div 
                          key={account.id}
                          className={`p-4 border rounded-lg transition-all ${
                            account.is_active ? 'border-blue-200 bg-blue-50' : 'border-slate-200'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-3">
                              <div className={`p-2 rounded-lg ${
                                account.is_active ? 'bg-blue-100' : 'bg-slate-100'
                              }`}>
                                <Phone className={`w-4 h-4 ${
                                  account.is_active ? 'text-blue-600' : 'text-slate-600'
                                }`} />
                              </div>
                              <div>
                                <p className="font-medium">{account.phone_number}</p>
                                <p className="text-sm text-slate-600">
                                  Criado: {new Date(account.created_at).toLocaleDateString('pt-BR')}
                                </p>
                              </div>
                            </div>
                            <div className="flex items-center space-x-2">
                              {getStatusBadge(account.status)}
                              {!account.is_active && account.status === 'authenticated' && (
                                <Button
                                  size="sm"
                                  onClick={() => activateAccount(account.id)}
                                >
                                  Ativar
                                </Button>
                              )}
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => deleteAccount(account.id)}
                              >
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Automation Tab */}
          <TabsContent value="automation" className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Automation Control */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Play className="w-5 h-5" />
                    Controle de Automação
                  </CardTitle>
                  <CardDescription>
                    Configure e execute a automação de membros
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {!activeAccount ? (
                    <Alert>
                      <AlertCircle className="h-4 w-4" />
                      <AlertDescription>
                        Conecte e ative uma conta primeiro na aba "Contas"
                      </AlertDescription>
                    </Alert>
                  ) : (
                    <>
                      <div className="space-y-2">
                        <Label htmlFor="source-groups">Grupos de Origem (um por linha)</Label>
                        <Textarea
                          id="source-groups"
                          placeholder="https://t.me/grupo1&#10;https://t.me/grupo2&#10;@nome_do_grupo"
                          value={sourceGroups}
                          onChange={(e) => setSourceGroups(e.target.value)}
                          rows={4}
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="target-group">Grupo de Destino</Label>
                        <Input
                          id="target-group"
                          placeholder="https://t.me/grupo_destino ou @nome_grupo"
                          value={targetGroup}
                          onChange={(e) => setTargetGroup(e.target.value)}
                        />
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label htmlFor="delay-min">Delay Mín (s)</Label>
                          <Input
                            id="delay-min"
                            type="number"
                            value={delayMin}
                            onChange={(e) => setDelayMin(parseInt(e.target.value))}
                            min="1"
                            max="60"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="delay-max">Delay Máx (s)</Label>
                          <Input
                            id="delay-max"
                            type="number"
                            value={delayMax}
                            onChange={(e) => setDelayMax(parseInt(e.target.value))}
                            min="1"
                            max="60"
                          />
                        </div>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="max-members">Máximo de Membros</Label>
                        <Input
                          id="max-members"
                          type="number"
                          value={maxMembers}
                          onChange={(e) => setMaxMembers(parseInt(e.target.value))}
                          min="1"
                          max="1000"
                        />
                      </div>

                      <Separator />

                      <div className="flex gap-2">
                        {!activeAutomation ? (
                          <Button
                            onClick={startAutomation}
                            disabled={loading || runningLogs.length > 0}
                            className="flex-1"
                          >
                            {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Play className="w-4 h-4 mr-2" />}
                            Iniciar Automação
                          </Button>
                        ) : (
                          <Button
                            onClick={stopAutomation}
                            variant="destructive"
                            className="flex-1"
                          >
                            <Square className="w-4 h-4 mr-2" />
                            Parar Automação
                          </Button>
                        )}
                      </div>

                      {runningLogs.length > 0 && (
                        <Alert>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          <AlertDescription>
                            {runningLogs.length} automação(ões) em execução
                          </AlertDescription>
                        </Alert>
                      )}
                    </>
                  )}
                </CardContent>
              </Card>

              {/* Status */}
              <Card>
                <CardHeader>
                  <CardTitle>Status em Tempo Real</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="text-center p-4 bg-blue-50 rounded-lg">
                        <UserPlus className="w-8 h-8 mx-auto mb-2 text-blue-600" />
                        <p className="text-2xl font-bold text-blue-900">{stats.today.total_added || 0}</p>
                        <p className="text-sm text-blue-600">Adicionados Hoje</p>
                      </div>
                      <div className="text-center p-4 bg-red-50 rounded-lg">
                        <XCircle className="w-8 h-8 mx-auto mb-2 text-red-600" />
                        <p className="text-2xl font-bold text-red-900">{stats.today.total_errors || 0}</p>
                        <p className="text-sm text-red-600">Erros Hoje</p>
                      </div>
                    </div>

                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span>Taxa de Sucesso</span>
                        <span>
                          {stats.today.total_added > 0 
                            ? Math.round((stats.today.total_added / (stats.today.total_added + stats.today.total_errors)) * 100)
                            : 0
                          }%
                        </span>
                      </div>
                      <Progress 
                        value={
                          stats.today.total_added > 0 
                            ? (stats.today.total_added / (stats.today.total_added + stats.today.total_errors)) * 100
                            : 0
                        } 
                        className="h-2"
                      />
                    </div>

                    {runningLogs.length > 0 && (
                      <div className="space-y-2">
                        <h4 className="font-medium">Execuções Ativas:</h4>
                        {runningLogs.map((log) => (
                          <div key={log.id} className="p-3 bg-blue-50 rounded-lg">
                            <div className="flex justify-between items-center mb-2">
                              <span className="font-medium">Para: {log.target_group}</span>
                              {getStatusBadge(log.status)}
                            </div>
                            <div className="text-sm text-slate-600">
                              <p>Adicionados: {log.members_added}</p>
                              <p>Erros: {log.errors}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Reports Tab */}
          <TabsContent value="reports" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Histórico de Automações</CardTitle>
                <CardDescription>
                  Últimas 50 execuções
                </CardDescription>
              </CardHeader>
              <CardContent>
                {automationLogs.length === 0 ? (
                  <div className="text-center py-6 text-slate-500">
                    <BarChart3 className="w-12 h-12 mx-auto mb-2 opacity-50" />
                    <p>Nenhuma automação executada ainda</p>
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Data/Hora</TableHead>
                        <TableHead>Conta</TableHead>
                        <TableHead>Grupo Destino</TableHead>
                        <TableHead>Adicionados</TableHead>
                        <TableHead>Erros</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Duração</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {automationLogs.map((log) => (
                        <TableRow key={log.id}>
                          <TableCell>
                            {new Date(log.started_at).toLocaleString('pt-BR')}
                          </TableCell>
                          <TableCell>{log.phone_number || '---'}</TableCell>
                          <TableCell className="max-w-xs truncate">{log.target_group}</TableCell>
                          <TableCell>
                            <Badge variant="secondary">{log.members_added}</Badge>
                          </TableCell>
                          <TableCell>
                            <Badge variant={log.errors > 0 ? "destructive" : "secondary"}>
                              {log.errors}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            {getStatusBadge(log.status)}
                          </TableCell>
                          <TableCell>
                            {log.finished_at 
                              ? `${Math.round((new Date(log.finished_at) - new Date(log.started_at)) / 1000)}s`
                              : '---'
                            }
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Settings Tab */}
          <TabsContent value="settings" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Configurações</CardTitle>
                <CardDescription>
                  Configure as credenciais da API do Telegram
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Alert>
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>
                    <strong>Configuração necessária:</strong> Para que a automação funcione, você precisa adicionar suas credenciais da API do Telegram no arquivo <code>/app/backend/.env</code>:
                    <br /><br />
                    <code>
                      TELEGRAM_API_ID=seu_api_id<br />
                      TELEGRAM_API_HASH=sua_api_hash
                    </code>
                    <br /><br />
                    Obtenha suas credenciais em: <a href="https://my.telegram.org/apps" target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">https://my.telegram.org/apps</a>
                  </AlertDescription>
                </Alert>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

export default App;