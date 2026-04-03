import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { FxResponse } from '../interfaces/FxResponse';
import { environment } from '../env/api';
@Injectable({
  providedIn: 'root',
})
export class FxService {
  
  private apiUrl = environment.apiUrl;
  constructor(private http: HttpClient) {}

  predict(devise:string,days:number): Observable<FxResponse> {
    return this.http.get<FxResponse>(`${this.apiUrl}/predict?devise=${devise}&days=${days}`);
  }
  }
