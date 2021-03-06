import { ChangeDetectionStrategy, Component, Input, ViewEncapsulation } from '@angular/core';
import { ApiRequestStatus } from '../interfaces/rpc.interfaces';
import { ErrorService } from '../pages/error.service';

@Component({
  selector: 'api-request-status',
  encapsulation: ViewEncapsulation.None,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ion-row justify-content-center *ngIf="status.loading">
      <ion-spinner [style.width]="size" [style.height]="size"></ion-spinner>
    </ion-row>
    <div *ngIf="status.error && !status.success">
      <p class="color-danger" [innerText]="errorService.getErrorMessage(status.error.error)"></p>
    </div>`,
})
export class ApiRequestStatusComponent {
  @Input() status: ApiRequestStatus;
  @Input() size = '36px';

  constructor(public errorService: ErrorService) {
  }
}
